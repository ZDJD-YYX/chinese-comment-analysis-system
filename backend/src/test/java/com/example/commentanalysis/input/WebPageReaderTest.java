package com.example.commentanalysis.input;

import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 网页正文提取测试。
 *
 * @author 闫宇星
 */
class WebPageReaderTest {

    @Test
    void extractKeepsArticleAndRemovesNoise() {
        String html = "<html><head><title> 测试 新闻 </title></head><body>"
                + "<header>网站头部 登录 注册</header>"
                + "<nav>首页 新闻 体育</nav>"
                + "<article>"
                + "  <h1>新能源汽车市场观察</h1>"
                + "  <p>首页 &gt; 新闻 &gt; 正文</p>"
                + "  <p>今年新能源汽车销量持续增长，用户满意度明显提升。</p>"
                + "  <p>多家厂商表示，续航与充电体验是用户最关心的两个方面。</p>"
                + "  <div class=\"ad\">广告 立即购买</div>"
                + "  <script>var tracking = 1;</script>"
                + "</article>"
                + "<footer>版权所有</footer>"
                + "</body></html>";

        Document document = Jsoup.parse(html, "https://example.com/news/1");
        WebPageContent content = WebPageReader.extract(document);
        String text = content.getText();

        assertTrue(text.contains("新能源汽车销量持续增长"));
        assertTrue(text.contains("续航与充电体验"));
        assertFalse(text.contains("网站头部"));
        assertFalse(text.contains("立即购买"));
        assertFalse(text.contains("var tracking"));
        assertFalse(text.contains("版权所有"));
        assertFalse(text.contains("首页 > 新闻"));
        assertTrue(content.getTitle().contains("测试 新闻"));
    }

    @Test
    void extractFallsBackToBodyWhenNoSemanticContainer() {
        String html = "<html><head><title>普通页面</title></head><body>"
                + "<div><p>这是一段没有任何语义容器的正文，仍然应当被完整提取出来用于情感分析。</p></div>"
                + "</body></html>";

        WebPageContent content = WebPageReader.extract(Jsoup.parse(html));
        assertTrue(content.getText().contains("没有任何语义容器的正文"));
    }

    @Test
    void extractPrefersBodyOverListCards() {
        // 模拟列表页：多个卡片 article + 一个真正的正文容器
        String html = "<html><head><title>列表页</title></head><body>"
                + "<div class=\"card-list\">"
                + "  <article class=\"card\"><a href=\"/a\">第一篇新闻标题某某某</a>"
                + "    <p>这里是第一篇新闻的摘要内容，用于吸引点击，正文并不在这里，只是简单介绍。</p></article>"
                + "  <article class=\"card\"><a href=\"/b\">第二篇新闻标题某某某</a>"
                + "    <p>这里是第二篇新闻的摘要内容，用于吸引点击，正文并不在这里，只是简单介绍。</p></article>"
                + "  <article class=\"card\"><a href=\"/c\">第三篇新闻标题某某某</a>"
                + "    <p>这里是第三篇新闻的摘要内容，用于吸引点击，正文并不在这里，只是简单介绍。</p></article>"
                + "</div>"
                + "<div class=\"article-content\">"
                + "  <p>正文第一段：这款耳机在实际使用中的降噪表现令人满意，通勤时几乎听不到外界噪声。</p>"
                + "  <p>正文第二段：续航方面，开启降噪后仍能坚持一整天，但充电盒体积偏大，携带略有不便。</p>"
                + "  <p>正文第三段：综合来看，音质与降噪达到预期，价格偏高是主要顾虑，建议等活动入手。</p>"
                + "</div>"
                + "</body></html>";

        WebPageContent content = WebPageReader.extract(Jsoup.parse(html, "https://example.com/list"));
        String text = content.getText();

        assertTrue(text.contains("正文第一段"));
        assertTrue(text.contains("降噪表现令人满意"));
        assertFalse(text.contains("第一篇新闻的摘要内容"), "不应把列表卡片当成正文");
        assertTrue(content.getParagraphCount() >= 3);
    }
}
