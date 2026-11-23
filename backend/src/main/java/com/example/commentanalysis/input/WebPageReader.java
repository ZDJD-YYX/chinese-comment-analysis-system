package com.example.commentanalysis.input;

import com.example.commentanalysis.common.BizException;
import com.example.commentanalysis.common.ResultCode;
import lombok.extern.slf4j.Slf4j;
import org.jsoup.Connection;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.nodes.Node;
import org.jsoup.nodes.TextNode;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.net.InetAddress;
import java.net.URI;
import java.net.URISyntaxException;
import java.net.UnknownHostException;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * 网页抓取与正文提取。
 *
 * <p>抓取前校验协议与目标地址，拒绝内网、回环、链路本地等受限地址，并逐跳校验重定向目标；
 * 抓取后移除脚本、导航、页头页脚、广告与推荐位等噪声节点，优先从 article / main 等
 * 正文容器中提取文本，保留段落换行，便于后续按段切分为评论。</p>
 *
 * @author 闫宇星
 */
@Slf4j
@Component
public class WebPageReader {

    /** 伪装主流桌面浏览器，避免站点直接返回精简页或 403 */
    private static final String USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            + "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36";

    /** 噪声节点选择器：导航、页头页脚、表单、广告、分享、推荐、分页等 */
    private static final String NOISE_SELECTOR =
            "script, style, noscript, iframe, svg, canvas, form, button, input, select, textarea, "
                    + "nav, header, footer, aside, "
                    + "[role=navigation], [role=banner], [role=contentinfo], [role=search], "
                    + "[hidden], [aria-hidden=true], "
                    + ".ad, .ads, .adsbygoogle, .advert, .advertisement, .advertising, "
                    + "[class*=advert], [id*=advert], "
                    + ".breadcrumb, .breadcrumbs, .pagination, .pager, .share, .social-share, "
                    + ".related, .recommend, .recommended, .sidebar, .toolbar, .cookie, "
                    + ".popup, .modal, .newsletter";

    /** 正文候选容器，按优先级排列 */
    private static final String[] CONTENT_SELECTORS = {
            "article", "main", "[role=main]",
            "#js_content", ".rich_media_content", ".article-content", ".article_content",
            ".post-content", ".entry-content", ".content-main", "#content", ".content"
    };

    /** 明确正文容器的选择器串，命中时额外加分 */
    private static final String CONTENT_HINT_SELECTOR = String.join(", ", CONTENT_SELECTORS);

    /**
     * 参与打分的块级候选。
     *
     * <p>不再"谁先命中就用谁"，而是把所有可能的正文块都算一遍分数再取最高，
     * 避免列表页里第一个 {@code <article>} 卡片被误当成正文。</p>
     */
    private static final String CANDIDATE_SELECTOR = CONTENT_HINT_SELECTOR
            + ", section, div, td";

    /** 单个页面参与打分的候选节点上限，防止超大页面拖慢抓取 */
    private static final int MAX_CANDIDATES = 600;

    /** 正文类名的正向关键词（命中加分） */
    private static final java.util.regex.Pattern POSITIVE_CLASS =
            java.util.regex.Pattern.compile(
                    "article|content|post|entry|main|text|detail|rich_media|story|doc|body");

    /** 正文类名的负向关键词（命中减分） */
    private static final java.util.regex.Pattern NEGATIVE_CLASS =
            java.util.regex.Pattern.compile(
                    "comment|recommend|related|hot|rank|sidebar|nav\\b|footer|header|copyright|"
                            + "share|advert|menu|breadcrumb|pagination|toolbar|popup|modal|subscribe|"
                            + "list|tag|guess|login");

    /** 正文容器最小文本长度，过短说明选错了节点 */
    private static final int MIN_CONTENT_LENGTH = 80;

    /** 链接密度超过该值时视为导航或列表页 */
    private static final double MAX_LINK_DENSITY = 0.5;

    /** 需要换段的块级标签 */
    private static final Set<String> BLOCK_TAGS = new HashSet<>(Arrays.asList(
            "p", "div", "section", "article", "main", "aside", "blockquote", "pre",
            "h1", "h2", "h3", "h4", "h5", "h6", "li", "ul", "ol", "dl", "dd", "dt",
            "table", "thead", "tbody", "tr", "td", "th", "figure", "figcaption", "hr"
    ));

    /** 常见界面文案，抓取时属于噪声，不作为评论分析 */
    private static final Set<String> BOILERPLATE = new HashSet<>(Arrays.asList(
            "广告", "推广", "分享", "收藏", "点赞", "在看", "写留言", "返回顶部",
            "展开全文", "阅读全文", "阅读原文", "登录", "注册", "首页", "上一页",
            "下一页", "上一篇", "下一篇", "相关阅读", "更多", "查看详情",
            "advertisement", "sponsored", "share", "login", "signin", "sign in",
            "subscribe", "read more"
    ));

    /** 抓取超时（毫秒），同时作用于连接与读取 */
    @Value("${app.input.fetch-timeout-ms:2000}")
    private int fetchTimeoutMs;

    /** 最大重定向次数 */
    @Value("${app.input.max-redirects:3}")
    private int maxRedirects;

    /** 单页最大下载字节数 */
    @Value("${app.input.max-body-size:3145728}")
    private int maxBodySize;

    /**
     * 抓取网页并提取正文。
     *
     * @param inputUrl 完整 http/https 链接
     * @return 标题、最终地址与正文
     */
    public WebPageContent fetch(String inputUrl) {
        String currentUrl = inputUrl;
        Map<String, String> cookies = new HashMap<>();
        for (int redirect = 0; redirect <= maxRedirects; redirect++) {
            URI uri = validatePublicUrl(currentUrl);
            Connection.Response response;
            try {
                response = Jsoup.connect(uri.toString())
                        .userAgent(USER_AGENT)
                        .header("Accept", "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8")
                        .header("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.6")
                        .timeout(fetchTimeoutMs)
                        .followRedirects(false)
                        .ignoreHttpErrors(true)
                        .ignoreContentType(true)
                        .maxBodySize(maxBodySize)
                        .cookies(cookies)
                        .execute();
            } catch (IOException e) {
                log.warn("网页抓取失败：url={}, 原因={}", currentUrl, e.getMessage());
                throw new BizException(ResultCode.INPUT_FETCH_FAILED,
                        "网页抓取失败，请确认链接可公开访问且网络通畅");
            }
            cookies.putAll(response.cookies());

            int status = response.statusCode();
            if (status >= 300 && status < 400) {
                String location = response.header("Location");
                if (location == null || location.trim().isEmpty()) {
                    throw new BizException(ResultCode.INPUT_FETCH_FAILED, "网页重定向地址缺失，无法解析");
                }
                currentUrl = resolveLocation(uri, location);
                continue;
            }
            if (status >= 400) {
                throw new BizException(ResultCode.INPUT_FETCH_FAILED,
                        "网页返回 HTTP " + status + "，无法解析");
            }
            String contentType = response.contentType();
            if (contentType != null && !isWebPage(contentType)) {
                throw new BizException(ResultCode.INPUT_FETCH_FAILED,
                        "该链接不是网页内容（" + contentType + "），暂不支持解析");
            }

            Document document;
            try {
                document = response.parse();
            } catch (IOException e) {
                log.warn("网页内容解析失败：url={}, 原因={}", currentUrl, e.getMessage());
                throw new BizException(ResultCode.INPUT_FETCH_FAILED, "网页内容读取失败，请稍后重试");
            }
            WebPageContent content = extract(document);
            content.setUrl(currentUrl);
            if (content.getTitle() == null || content.getTitle().isEmpty()) {
                content.setTitle(uri.getHost());
            }
            log.info("网页解析完成：url={}, 标题={}, 正文字符数={}",
                    currentUrl, content.getTitle(), content.getText().length());
            return content;
        }
        throw new BizException(ResultCode.INPUT_FETCH_FAILED, "网页重定向次数过多，无法解析");
    }

    /**
     * 从已解析的文档中提取正文（供抓取流程与单元测试共用）。
     *
     * @param document 网页文档
     * @return 正文内容（url 由抓取方回填）
     */
    public static WebPageContent extract(Document document) {
        String title = document.title() == null ? "" : InputTextProcessor.normalize(document.title());
        document.select(NOISE_SELECTOR).remove();

        Element container = chooseContentContainer(document);
        StringBuilder builder = new StringBuilder();
        appendText(container, builder);

        StringBuilder text = new StringBuilder();
        for (String line : InputTextProcessor.normalize(builder.toString()).split("\n")) {
            String value = line.trim();
            if (value.isEmpty() || isBoilerplate(value) || isBreadcrumb(value)) {
                continue;
            }
            if (text.length() > 0) {
                text.append('\n');
            }
            text.append(value);
        }

        WebPageContent content = new WebPageContent();
        content.setTitle(title);
        content.setText(text.toString());
        content.setParagraphCount(container == null ? 0 : container.select("p").size());
        content.setLinkDensity(container == null ? 0D : linkDensity(container, builder.length()));
        return content;
    }

    /**
     * 选择正文容器：对所有候选块打分，取得分最高的节点。
     *
     * <p>打分综合文本长度、链接密度、段落数、标点密度与类名权重，
     * 有效避免把导航、推荐位、列表卡片当成正文。</p>
     *
     * @param document 文档
     * @return 正文节点
     */
    private static Element chooseContentContainer(Document document) {
        Element body = document.body();
        int bodyTextLength = body == null ? 0 : body.text().length();

        Element best = null;
        double bestScore = Double.NEGATIVE_INFINITY;
        int inspected = 0;
        for (Element element : document.select(CANDIDATE_SELECTOR)) {
            if (inspected++ >= MAX_CANDIDATES) {
                break;
            }
            // 叶子节点不可能是正文容器，先跳过以降低打分开销
            if (element.childNodeSize() == 0) {
                continue;
            }
            String text = element.text();
            if (text.length() < MIN_CONTENT_LENGTH) {
                continue;
            }
            double score = scoreCandidate(element, text, bodyTextLength);
            if (score > bestScore) {
                bestScore = score;
                best = element;
            }
        }
        if (best != null) {
            return best;
        }
        return body == null ? document : body;
    }

    /**
     * 为候选容器打分。
     *
     * @param element        候选节点
     * @param text           候选节点的纯文本
     * @param bodyTextLength 整页文本长度，用于识别"覆盖全页的包裹层"
     * @return 得分，越高越像正文
     */
    private static double scoreCandidate(Element element, String text, int bodyTextLength) {
        int textLength = text.length();
        if (textLength < MIN_CONTENT_LENGTH) {
            return Double.NEGATIVE_INFINITY;
        }

        // 基础分：文本越长越像正文，但超过 8000 字后不再线性增长
        double score = Math.min(textLength, 8000) / 10.0D;

        double density = linkDensity(element, textLength);
        // 链接密度越高越可能是导航、目录或列表，直接按比例削减并额外扣分
        score *= (1 - Math.min(density, 0.9D));
        score -= density * 400;

        // 段落数：正文通常由多个 <p> 组成
        int paragraphs = element.select("p").size();
        score += Math.min(paragraphs, 30) * 12;

        // 标点密度：正文逗号句号多，菜单与按钮几乎没有
        score += Math.min(countPunctuation(text), 400) * 0.6D;

        // 标签权重
        String tag = element.tagName().toLowerCase(Locale.ROOT);
        if ("article".equals(tag)) {
            score += 120;
        } else if ("main".equals(tag)) {
            score += 90;
        } else if ("section".equals(tag)) {
            score += 30;
        } else if ("td".equals(tag)) {
            score -= 60;
        }

        // 命中明确的正文容器选择器时额外加分（如微信公众号的 #js_content）
        if (element.is(CONTENT_HINT_SELECTOR)) {
            score += 200;
        }

        String classId = (element.className() + " " + element.id()).toLowerCase(Locale.ROOT);
        if (!classId.trim().isEmpty()) {
            if (NEGATIVE_CLASS.matcher(classId).find()) {
                score -= 400;
            } else if (POSITIVE_CLASS.matcher(classId).find()) {
                score += 150;
            }
        }

        // 覆盖整页、又带不少链接的包裹层，说明把导航一起包进来了
        if (bodyTextLength > 0) {
            double ratio = textLength / (double) bodyTextLength;
            if (ratio > 0.85D && density > 0.12D) {
                score -= 500;
            }
        }
        return score;
    }

    /**
     * 计算链接密度：链接内文字长度 / 容器文字长度。
     *
     * @param element    容器
     * @param textLength 容器文本长度（由调用方传入，避免重复遍历）
     * @return 0～1 的链接密度
     */
    private static double linkDensity(Element element, int textLength) {
        if (textLength <= 0) {
            return 0D;
        }
        int linkLength = 0;
        for (Element link : element.select("a")) {
            linkLength += link.text().length();
        }
        return Math.min(1D, linkLength / (double) textLength);
    }

    /**
     * 统计中英文常用标点数量，用于判断文本是否像自然语言正文。
     *
     * @param text 文本
     * @return 标点数量
     */
    private static int countPunctuation(String text) {
        int count = 0;
        for (int i = 0; i < text.length(); i++) {
            char value = text.charAt(i);
            if (value == '，' || value == '。' || value == '！' || value == '？'
                    || value == '；' || value == '：' || value == '、'
                    || value == ',' || value == '.' || value == '!' || value == '?'
                    || value == ';' || value == ':') {
                count++;
            }
        }
        return count;
    }

    /**
     * 判断抓取结果是否可能抽错了内容。
     *
     * <p>链接密度过高、段落数过少或正文过短时认为可疑，由前端提示用户确认。</p>
     *
     * @param content 抓取结果
     * @return true 表示建议用户确认
     */
    public static boolean isSuspect(WebPageContent content) {
        if (content == null || content.getText() == null) {
            return true;
        }
        int length = content.getText().length();
        if (length < MIN_CONTENT_LENGTH * 2) {
            return true;
        }
        if (content.getLinkDensity() > MAX_LINK_DENSITY) {
            return true;
        }
        return length > 400 && content.getParagraphCount() == 0;
    }

    /**
     * 递归提取文本，块级元素前后补换行，保留段落结构。
     *
     * @param node    当前节点
     * @param builder 文本缓冲
     */
    private static void appendText(Node node, StringBuilder builder) {
        if (node instanceof TextNode) {
            builder.append(((TextNode) node).getWholeText());
            return;
        }
        if (!(node instanceof Element)) {
            return;
        }
        Element element = (Element) node;
        String tag = element.tagName().toLowerCase(Locale.ROOT);
        if ("br".equals(tag)) {
            builder.append('\n');
            return;
        }
        boolean block = BLOCK_TAGS.contains(tag);
        if (block) {
            appendNewline(builder);
        }
        for (Node child : element.childNodes()) {
            appendText(child, builder);
        }
        if (block) {
            appendNewline(builder);
        }
    }

    /**
     * 追加换行，避免连续空行。
     *
     * @param builder 文本缓冲
     */
    private static void appendNewline(StringBuilder builder) {
        if (builder.length() > 0 && builder.charAt(builder.length() - 1) != '\n') {
            builder.append('\n');
        }
    }

    /**
     * 判断是否为纯界面文案。
     *
     * @param line 单行文本
     * @return 属于界面噪声返回 true
     */
    private static boolean isBoilerplate(String line) {
        String key = line.replaceAll("[\\s|·•\\-_/]+", "").toLowerCase(Locale.ROOT);
        return BOILERPLATE.contains(line.toLowerCase(Locale.ROOT)) || BOILERPLATE.contains(key);
    }

    /**
     * 判断是否为「首页 &gt; 频道 &gt; 正文」这类面包屑行。
     *
     * @param line 单行文本
     * @return 面包屑返回 true
     */
    private static boolean isBreadcrumb(String line) {
        if (line.length() >= 60) {
            return false;
        }
        boolean hasSeparator = line.indexOf('>') >= 0 || line.indexOf('›') >= 0 || line.indexOf('»') >= 0;
        return hasSeparator && line.split("[>›»]").length >= 3;
    }

    /**
     * 校验链接是否允许抓取。
     *
     * @param url 链接
     * @return 规范化后的 URI
     */
    private static URI validatePublicUrl(String url) {
        URI uri;
        try {
            uri = new URI(url);
        } catch (URISyntaxException e) {
            throw new BizException(ResultCode.INPUT_URL_INVALID);
        }
        String scheme = uri.getScheme();
        if (scheme == null || (!"http".equalsIgnoreCase(scheme) && !"https".equalsIgnoreCase(scheme))) {
            throw new BizException(ResultCode.INPUT_URL_INVALID, "仅支持以 http:// 或 https:// 开头的网页链接");
        }
        String host = uri.getHost();
        if (host == null || host.isEmpty()) {
            throw new BizException(ResultCode.INPUT_URL_INVALID);
        }
        String lowerHost = host.toLowerCase(Locale.ROOT);
        if ("localhost".equals(lowerHost) || lowerHost.endsWith(".localhost")
                || lowerHost.endsWith(".local") || lowerHost.endsWith(".internal")) {
            throw new BizException(ResultCode.INPUT_URL_BLOCKED);
        }
        try {
            for (InetAddress address : InetAddress.getAllByName(host)) {
                if (isBlocked(address)) {
                    throw new BizException(ResultCode.INPUT_URL_BLOCKED);
                }
            }
        } catch (UnknownHostException e) {
            throw new BizException(ResultCode.INPUT_FETCH_FAILED, "无法解析该链接的域名，请检查后重试");
        }
        return uri;
    }

    /**
     * 判断地址是否属于内网、回环、链路本地等受限网段。
     *
     * @param address 解析后的地址
     * @return 受限返回 true
     */
    private static boolean isBlocked(InetAddress address) {
        if (address.isAnyLocalAddress() || address.isLoopbackAddress()
                || address.isLinkLocalAddress() || address.isSiteLocalAddress()
                || address.isMulticastAddress()) {
            return true;
        }
        byte[] bytes = address.getAddress();
        if (bytes.length == 4) {
            int first = bytes[0] & 0xff;
            int second = bytes[1] & 0xff;
            int third = bytes[2] & 0xff;
            // 0.0.0.0/8、运营商级 NAT 100.64/10、192.0.0/24、198.18/15、链路本地 169.254/16
            return first == 0
                    || (first == 100 && second >= 64 && second <= 127)
                    || (first == 192 && second == 0 && third == 0)
                    || (first == 198 && (second == 18 || second == 19))
                    || (first == 169 && second == 254);
        }
        if (bytes.length == 16) {
            int first = bytes[0] & 0xff;
            int second = bytes[1] & 0xff;
            // IPv6 唯一本地地址 fc00::/7 与链路本地 fe80::/10
            return (first & 0xfe) == 0xfc || (first == 0xfe && (second & 0xc0) == 0x80);
        }
        return false;
    }

    /**
     * 解析重定向地址（支持相对路径）。
     *
     * @param base     当前地址
     * @param location 重定向头
     * @return 下一跳完整地址
     */
    private static String resolveLocation(URI base, String location) {
        try {
            return base.resolve(location.trim()).toString();
        } catch (IllegalArgumentException e) {
            throw new BizException(ResultCode.INPUT_FETCH_FAILED, "网页重定向地址无法解析");
        }
    }

    /**
     * 判断响应的 Content-Type 是否可作为网页解析。
     *
     * @param contentType 响应类型
     * @return 可作为网页解析返回 true
     */
    private static boolean isWebPage(String contentType) {
        String value = contentType.toLowerCase(Locale.ROOT);
        return value.contains("html") || value.startsWith("text/");
    }
}
