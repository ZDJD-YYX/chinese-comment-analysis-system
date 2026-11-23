# -*- coding: utf-8 -*-
"""生成《软件工程实验报告 - 详细设计报告》（中文评论智能分析系统）。"""
import os
from docx import Document
from docx.shared import Pt, Cm, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(BASE, '文档', '1792460254987-软件工程实验报告模板 -详细设计报告.docx')
DST = os.path.join(BASE, '文档', '软件工程实验报告-详细设计-中文评论智能分析系统.docx')
FIG = os.path.join(BASE, '_figs_dd')

doc = Document(TPL)


# ---------------------------------------------------------------------
# 基础排版工具
# ---------------------------------------------------------------------
def set_run_font(run, size=12, bold=False, ascii_font='Times New Roman',
                 east='宋体', color=None):
    run.font.name = ascii_font
    run.font.size = Pt(size)
    run.bold = bold
    run._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), east)
    if color:
        run.font.color.rgb = color


def clear_runs(p):
    for r in list(p.runs):
        r._element.getparent().remove(r._element)


def replace_cover(p, text, size=16):
    clear_runs(p)
    r = p.add_run(text)
    set_run_font(r, size=size, bold=True, ascii_font='楷体_GB2312', east='楷体_GB2312')


def body(txt, indent=True, size=12, space_after=4, bold_prefix=None, align='justify'):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.first_line_indent = Cm(0.85) if indent else Cm(0)
    pf.line_spacing = 1.45
    pf.space_before = Pt(0)
    pf.space_after = Pt(space_after)
    p.alignment = {'justify': WD_ALIGN_PARAGRAPH.JUSTIFY,
                   'left': WD_ALIGN_PARAGRAPH.LEFT,
                   'center': WD_ALIGN_PARAGRAPH.CENTER}[align]
    if bold_prefix:
        r = p.add_run(bold_prefix)
        set_run_font(r, size=size, bold=True)
    r = p.add_run(txt)
    set_run_font(r, size=size)
    return p


def h2(txt):
    p = doc.add_paragraph(txt, style='Heading 2')
    pf = p.paragraph_format
    pf.space_before = Pt(18)
    pf.space_after = Pt(10)
    pf.line_spacing = 1.2
    pf.keep_with_next = True
    for r in p.runs:
        set_run_font(r, size=18, bold=True, east='宋体')
    return p


def h3(txt):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.first_line_indent = Cm(0.85)
    pf.space_before = Pt(10)
    pf.space_after = Pt(4)
    pf.keep_with_next = True
    r = p.add_run(txt)
    set_run_font(r, size=12, bold=True)
    return p


def caption(txt):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf = p.paragraph_format
    pf.space_before = Pt(2)
    pf.space_after = Pt(8)
    pf.keep_with_next = False
    r = p.add_run(txt)
    set_run_font(r, size=9, bold=True)
    return p


def figure(name, cap, width=6.1):
    path = os.path.join(FIG, name)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(path, width=Inches(width))
    caption(cap)


def shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill)
    tcPr.append(shd)


def cell_margins(table, left=0.06, right=0.06, top=0.02, bottom=0.02):
    tblPr = table._tbl.tblPr
    mar = OxmlElement('w:tblCellMar')
    for tag, val in (('top', top), ('left', left), ('bottom', bottom), ('right', right)):
        e = OxmlElement(f'w:{tag}')
        e.set(qn('w:w'), str(int(val * 567)))
        e.set(qn('w:type'), 'dxa')
        mar.append(e)
    tblPr.append(mar)


def repeat_header(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement('w:tblHeader')
    el.set(qn('w:val'), 'true')
    trPr.append(el)


def table(headers, rows, widths, size=8, header_fill='DCE6F1', align_left=True):
    # 表题与表格保持在同一页
    if doc.paragraphs:
        doc.paragraphs[-1].paragraph_format.keep_with_next = True
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = 'Table Grid'
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    cell_margins(t)
    # 固定表格布局，保证列宽按设计值生效
    tblPr = t._tbl.tblPr
    layout = OxmlElement('w:tblLayout')
    layout.set(qn('w:type'), 'fixed')
    tblPr.append(layout)
    for i, w in enumerate(widths):
        t.columns[i].width = Cm(w)
    hdr = t.rows[0]
    repeat_header(hdr)
    for i, h in enumerate(headers):
        c = hdr.cells[i]
        c.width = Cm(widths[i])
        shade(c, header_fill)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(str(h))
        set_run_font(r, size=size, bold=True)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            c = cells[i]
            c.width = Cm(widths[i])
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.15
            if i == 0:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            elif align_left and i == len(headers) - 1:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(str(v))
            set_run_font(r, size=size)
    # 短表尽量不跨页；长表允许分页并重复表头
    if len(rows) <= 12:
        for idx, row in enumerate(t.rows):
            trPr = row._tr.get_or_add_trPr()
            trPr.append(OxmlElement('w:cantSplit'))
            if idx < len(t.rows) - 1:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        p.paragraph_format.keep_with_next = True
    # 表后留白
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.0
    return t


def code_block(lines, size=9):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.left_indent = Cm(0.6)
    pf.right_indent = Cm(0.3)
    pf.space_before = Pt(4)
    pf.space_after = Pt(6)
    pf.line_spacing = 1.0
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), 'F4F4F4')
    pPr.append(shd)
    for i, line in enumerate(lines):
        r = p.add_run(line)
        set_run_font(r, size=size, ascii_font='Consolas', east='宋体')
        if i < len(lines) - 1:
            r.add_break()


# ---------------------------------------------------------------------
# 封面信息 + 删除模板正文
# ---------------------------------------------------------------------
cover = doc.paragraphs
replace_cover(cover[23], '实验名称：项目详细设计报告')
replace_cover(cover[24], '姓    名：  闫宇星')
replace_cover(cover[25], '学    号：  2305006422')
replace_cover(cover[26], '班    级：  软工23101')

body_el = doc.element.body
for p in list(doc.paragraphs)[27:]:
    body_el.remove(p._p)

# ---------------------------------------------------------------------
# 一、引言
# ---------------------------------------------------------------------
doc.add_page_break()
h2('一、引言')

h3('1.1 编写目的')
body('本详细设计说明书依据《软件需求规格说明书（中文评论智能分析系统）》与《概要设计说明书》，对系统各模块的内部数据结构、类与方法签名、算法逻辑、接口参数、数据库表结构与异常处理策略作出可直接编码的实现级定义。文档面向后续的编码、单元测试与集成测试，是开发人员编写代码、测试人员设计用例的直接依据，也是评审阶段判断“设计是否具备落地条件”的检查清单。')
body('与概要设计关注“系统由哪些模块组成、模块之间如何划分”不同，本文档回答“每个模块内部由哪些类实现、方法如何签名、数据如何流转、异常如何收敛”。文中所有类名、方法名、接口路径、表名与字段名均与工程代码一一对应，可直接在 backend/src/main/java 与 static 目录中定位。')
body('阅读约定：① 统一响应结构固定为 {code, message, data}，code = 0 表示成功；② 分页请求统一使用 pageNum（从 1 开始）与 pageSize（上限 200），响应统一使用 PageVO；③ 所有时间字段使用 LocalDateTime，数据库使用 DATETIME；④ 置信度、占比、TF-IDF 权重统一保留四位小数，数据库使用 DECIMAL 类型；⑤ 文中“业务层”指 controller + service，“智能服务层”指 ai 包。')

h3('1.2 术语定义与参考资料')
body('本文档使用的专业术语及其在本系统中的具体含义如表 1-1 所示。')
caption('表 1-1  术语定义表')
table(['术语', '含义与在本系统中的用法'], [
    ['B/S 架构', '浏览器/服务器架构。本系统前端为浏览器页面，后端为 Spring Boot 服务，静态资源随 JAR 发布。'],
    ['RESTful API', '以资源为中心、用 HTTP 方法表达操作的接口风格。本系统 15 个接口均遵循该风格，统一返回 JSON。'],
    ['ORM', '对象关系映射。本系统通过 MyBatis-Plus 将实体类与数据表映射，避免手写样板 CRUD。'],
    ['DTO / VO', '数据传输对象 / 视图对象。DTO 接收请求参数（LoginDTO、RegisterDTO），VO 封装响应数据（如 ResultVO、ProgressVO）。'],
    ['单例（Singleton）', '全局仅保留一个实例。ModelRepository 在应用启动时加载模型并常驻，运行期复用同一 ZooModel 与 Predictor。'],
    ['TorchScript', 'PyTorch 的静态图导出格式。训练脚本将 BERT 模型导出为 model.pt，后端通过 DJL 加载，无需 Python 运行时。'],
    ['DJL', 'Deep Java Library，Java 端深度学习推理框架。本系统使用其 PyTorch Engine 与 CPU 本地库执行前向推理。'],
    ['BERT / WordPiece', '预训练中文语言模型及其子词切分算法。后端 BertTokenizer 复现 HuggingFace 分词流程，输出 input_ids 等三组张量。'],
    ['TF-IDF', '词频-逆文档频率。用于计算热点词权重，权重越高代表该词在任务语料中越具代表性。'],
    ['BCrypt', '自带随机盐的慢哈希算法。用户密码以 BCrypt 哈希存储，历史 SHA-256 哈希在登录成功后自动升级。'],
    ['逻辑删除', '以 is_deleted 标记代替物理删除。analysis_task 删除后不物理移除，查询由 MyBatis-Plus 自动过滤。'],
    ['批量推理', '一次前向计算处理多条文本。默认 batch_size = 32，兼顾 CPU 吞吐与内存占用。'],
    ['会话（Session）', '服务端保存登录态的机制。登录成功后写入 HttpSession，后续请求由 AuthInterceptor 校验。'],
], [3.4, 12.4], size=8.5)
body('本文档引用的标准、规范与前期文档如表 1-2 所示。')
caption('表 1-2  参考资料表')
table(['编号', '资料名称', '用途'], [
    ['R1', 'GB/T 8567—2006《计算机软件文档编制规范》', '详细设计说明书的章节组织与编写要求'],
    ['R2', 'GB/T 9385—2008《计算机软件需求规格说明规范》', '需求条目与验收标准的表述方式'],
    ['R3', '《软件需求规格说明书（中文评论智能分析系统）》V1.1', '功能需求、非功能需求与数据需求的来源'],
    ['R4', '《软件工程实验报告-概要设计-中文评论智能分析系统》', '分层架构、模块划分、接口概要与概念模型的来源'],
    ['R5', '《阿里巴巴 Java 开发手册》（嵩山版）', '命名、注释、异常、日志与集合使用规范'],
    ['R6', 'Spring Boot 2.7、MyBatis-Plus 3.5、DJL 0.38 官方文档', '框架配置、分页插件、模型加载与推理 API 的依据'],
], [1.4, 9.0, 5.4], size=8.5)

# ---------------------------------------------------------------------
# 二、系统架构与模块回顾
# ---------------------------------------------------------------------
h2('二、系统架构与模块回顾（简述）')

h3('2.1 分层架构回顾')
body('系统沿用概要设计确定的“分层架构 + B/S 前后端分离”风格，自下而上划分为四层：表示层为浏览器端原生 HTML5/CSS3/JavaScript 页面，使用本地化的 ECharts 绘制情感饼图与词云；业务层为 Spring Boot 2.7.15 应用，内部再分 Controller（接口与参数校验）与 Service（业务规则与事务）两级；数据访问层为 MyBatis-Plus Mapper 与 HikariCP 连接池，访问 MySQL 8.0；智能服务层为独立的 ai 包，通过 DJL + PyTorch Engine（CPU）加载 TorchScript 中文情感分类模型。')
body('部署形态为单机 B/S：前端静态资源打包在 JAR 的 static 目录，由内嵌 Tomcat 提供，不依赖 Nginx；模型文件位于 JAR 之外的文件系统目录（配置项 app.model.path），便于替换与升级；全部数据保存在本地 MySQL，不向外部服务发送评论原文。')
body('工程规模：后端主代码 57 个 Java 文件、约 5 946 行；前端 9 个文件（1 个 HTML、4 个 JS、2 个 CSS、2 个本地图表库）、约 5 258 行。代码规模与概要设计的 7 模块划分一致，未引入微服务、消息队列等超出单机范围的组件。')

h3('2.2 代码包结构')
body('后端代码按职责划分为 controller、service（含 impl）、scheduler、ai、mapper、entity、dto、vo、config、common 十个包，另有一个启动类。包结构与类清单如图 2-1 所示。')
figure('dd_package.png', '图 2-1  后端代码包结构图', 6.15)
body('包依赖遵循单向原则：controller 只依赖 service 接口与 vo；service.impl 依赖 mapper、entity 与 scheduler；scheduler 依赖 ai 门面与 mapper，不依赖 controller；ai 包不依赖任何业务包，仅依赖 config 中的属性类与 vo 中的模型信息对象；common 与 config 为横切包，可被各层引用。该约束保证替换推理实现（如改用 ONNX 或本地 Python 服务）时，业务代码不需要修改。')

h3('2.3 运行期组件与部署')
body('运行期组件及其协作关系如图 2-2 所示。浏览器通过 HTTP/JSON 调用 Controller；Controller 委托 Service 完成业务规则；Service 通过 Mapper 读写 MySQL，并在需要分析时向 InferenceScheduler 提交异步任务；Scheduler 使用专用线程池执行批量推理，调用 SentimentInferenceService 门面；门面内部依次使用 TextPreprocessor、BertTokenizer、ModelRepository 与 KeywordExtractor。')
figure('dd_component.png', '图 2-2  系统组件图（运行期）', 6.2)
body('关键运行参数：HTTP 端口 8080；会话有效期 2 小时，Cookie 设置 HttpOnly 与 SameSite=Lax；HikariCP 最小空闲 5、最大连接 20、连接超时 30 秒；推理线程池核心 2、最大 4、队列容量 100，队列满时直接拒绝并提示用户稍后重试；上传单文件上限 50 MB；模型目录必须为纯 ASCII 路径（libtorch 在 Windows 下无法打开含中文的路径）。')

# ---------------------------------------------------------------------
# 三、业务模块详细设计
# ---------------------------------------------------------------------
h2('三、业务模块详细设计（常规软件部分）')

h3('3.1 核心类图（Class Diagram）')
body('业务模块采用“Controller → Service 接口 → ServiceImpl → Mapper → Entity”的五段式结构。Controller 只负责参数接收、@Valid 校验与响应封装；Service 接口定义业务能力，ServiceImpl 承担业务规则、事务边界与异常抛出；Mapper 继承 MyBatis-Plus BaseMapper 获得通用 CRUD，并对批量插入、反连接查询、聚合统计等场景补充注解 SQL；Entity 通过 @TableName 与数据表映射。核心类及其关系如图 3-1 所示。')
figure('dd_class.png', '图 3-1  业务模块核心类图', 6.2)
body('类之间的关系包括三类：① 依赖——Controller 持有 Service 接口引用，通过构造器注入（@RequiredArgsConstructor）；② 实现——四个 ServiceImpl 分别实现对应接口，其中 AnalysisTaskServiceImpl 同时继承 MyBatis-Plus 的 ServiceImpl<AnalysisTaskMapper, AnalysisTask>，复用通用分页与 CRUD；③ 组合/关联——ServiceImpl 持有多个 Mapper 与调度器，InferenceScheduler 持有推理门面、五个 Mapper、线程池与 TransactionTemplate。')
body('核心类的职责与关键方法如表 3-1 所示。')
caption('表 3-1  核心类职责与关键方法')
table(['类名', '层次/类型', '关键方法与字段', '主要依赖'], [
    ['UserController', '控制类', 'login(dto, session)、register(dto, session)、me(session)、logout(session)', 'UserService、HttpSession'],
    ['FileController', '控制类', 'upload(MultipartFile)', 'FileService、AnalysisTaskService'],
    ['TaskController', '控制类', 'list、detail、delete、run、progress、cancel', 'AnalysisTaskService'],
    ['ResultController', '控制类', 'list、statistics、keywords、export', 'ResultService'],
    ['UserServiceImpl', '业务实现', 'login、register、matches、upgradePassword、isLocked', 'SysUserMapper、BCryptPasswordEncoder'],
    ['FileServiceImpl', '业务实现', 'uploadAndParse、streamParseAndInsert、detectCsvCharset、clean；内部类 ParseListener', 'AnalysisTaskMapper、CommentDataMapper、SysUserMapper'],
    ['AnalysisTaskServiceImpl', '业务实现', 'createTask、pageTasks、startInference、cancelTask、getProgress', 'AnalysisTaskMapper、InferenceScheduler'],
    ['ResultServiceImpl', '业务实现', 'pageResults、statistics、keywords、export', '五个 Mapper、InferenceProperties'],
    ['InferenceScheduler', '调度组件', 'submitAsync、run、cancel、processBatch、finishSuccess', '推理门面、五个 Mapper、线程池、TransactionTemplate'],
    ['6 个 Mapper', '数据访问', 'insertBatch、selectPendingComments、selectExportPage、selectSummary、incrementProgress', 'BaseMapper、实体类'],
    ['6 个实体', '数据实体', '字段与表字段一一对应；@TableId、@TableLogic、@TableName', '无'],
], [3.6, 2.2, 6.6, 3.4], size=8)
body('设计要点：Controller 不写 try-catch，业务异常统一抛出 BizException，由 GlobalExceptionHandler 转换；ServiceImpl 的公共方法才声明事务，推理与关键词提取等耗时操作放在事务之外；所有返回给前端的对象均为 vo 包中的视图对象，实体对象不直接暴露，避免密码哈希等敏感字段外泄。')

h3('3.2 关键业务时序图与逻辑')

body('（1）用户登录与会话鉴权。', indent=True, bold_prefix='')
body('登录流程如图 3-2 所示。系统为单用户（单管理员）模式，账号不存在与密码错误统一返回错误码 1001，避免账号枚举；连续 5 次失败后锁定 5 分钟；密码使用 BCrypt 校验，历史“随机盐 + 单轮 SHA-256”的账号在首次登录成功后透明升级为 BCrypt。')
figure('dd_seq_login.png', '图 3-2  用户登录与会话鉴权时序图', 6.2)
body('UserServiceImpl.login 的核心逻辑如下：')
code_block([
    'public LoginVO login(LoginDTO dto) {',
    '    String key = dto.getUsername().trim().toLowerCase(Locale.ROOT);',
    '    if (isLocked(key))',
    '        throw new BizException(LOGIN_FAILED, "登录失败次数过多，请 5 分钟后再试");',
    '    SysUser user = getByUsername(dto.getUsername().trim());',
    '    boolean matched = user != null && matches(dto.getPassword(), user);',
    '    if (!matched) { recordFailure(key); throw new BizException(LOGIN_FAILED); }',
    '    if (user.getStatus() == null || user.getStatus() != STATUS_ENABLED)',
    '        throw new BizException(LOGIN_FAILED, "账号已停用，请联系管理员");',
    '    clearFailures(key);',
    '    if (!isBcrypt(user.getPasswordHash())) upgradePassword(user, dto.getPassword());',
    '    // 刷新 last_login_time 后返回 LoginVO（仅 userId、username）',
    '}',
], size=8.6)
body('登录成功后，UserController 把 userId 与 username 写入 HttpSession（键为 LOGIN_USER_ID、LOGIN_USERNAME）；后续所有 /api/** 请求（登录、注册除外）由 AuthInterceptor 在 preHandle 中校验会话，缺失时直接返回 HTTP 401 与统一 JSON，不进入 Controller。')

body('（2）评论文件上传与解析。', indent=True)
body('上传解析是本系统常规业务中最复杂的一段：需要在 50 MB 文件、万级行数下保持内存可控，并自动识别评论列、处理 UTF-8/GBK 编码差异。流程如图 3-3 所示。')
figure('dd_seq_upload.png', '图 3-3  评论文件上传解析时序图', 6.2)
body('解析算法的关键步骤如下：')
body('① 前置校验：文件非空、扩展名属于 {xlsx, xls, csv}、大小不超过 50 MB，否则分别返回 2001/2002。')
body('② 创建任务：写入 analysis_task，状态 PENDING，同时快照 batch_size，任务名默认取文件名去扩展名并按列宽截断。')
body('③ 流式解析：EasyExcel 以 headRowNumber(0) 读取，每行以 Map<列序号, 单元格文本> 回调 ParseListener；前 200 行先缓冲用于识别评论列，其余行边读边处理。')
body('④ 字符集嗅探（仅 CSV）：按 BOM（UTF-8/UTF-16）优先；无 BOM 时严格尝试 UTF-8 解码，失败则按 GBK/ANSI 处理，避免中文 Windows 下 Excel 导出的 CSV 整体乱码。')
body('⑤ 评论列识别：先按表头关键词（评论、内容、文本、评价、留言、comment、content、text、review）打分，排除“编号、序号、时间、评分、名称、用户”等元信息列，得分 = 命中关键词长度 × 100 − 列名长度；若首行像表头但未命中关键词，则按各列平均文本长度推断（要求含字母或汉字且平均长度 ≥ 2）；若首行本身是数据，则取第 0 列并从首行开始处理。')
body('⑥ 清洗与入库：全角空格归一、连续空白折叠、去首尾空白，超长文本按 max-text-length（512）截断；空白行计入 filteredCount；有效评论每 1 000 条执行一次多值 INSERT。')
body('⑦ 失败清理：分批提交后没有整体事务，解析或入库异常时调用 deletePhysically(taskId)，借助外键 ON DELETE CASCADE 清理半成品数据，再把业务异常抛给全局处理器。')
body('⑧ 提交推理：FileController 在解析事务提交后调用 startInference(taskId)，避免异步线程读不到尚未提交的评论数据。')
body('ParseListener 的核心逻辑可概括为：')
code_block([
    'void invoke(row, context) {',
    '    currentRowNo++;',
    '    if (!columnDecided) {',
    '        buffer.add(row);',
    '        if (buffer.size() >= 200) decideColumn();',
    '        return;',
    '    }',
    '    processRow(row, currentRowNo);',
    '}',
    'void decideColumn() {',
    '    column = detectCommentColumn(firstRow);',
    '    if (column >= 0) startIndex = 1;',
    '    else if (looksLikeHeaderRow(firstRow)) {',
    '        column = guessCommentColumn(buffer, 1); startIndex = 1;',
    '    } else { column = 0; startIndex = 0; }',
    '    for (i = startIndex; i < buffer.size(); i++)',
    '        processRow(buffer.get(i), i + 1);',
    '}',
], size=8.2)

body('（3）异步推理调度与进度查询。', indent=True)
body('推理任务在专用线程池中执行，上传与查询接口立即返回；前端每 1.5 秒轮询一次进度，直到任务进入 SUCCESS / FAILED / CANCELED 终态。流程如图 3-4 所示。')
figure('dd_seq_infer.png', '图 3-4  异步推理调度与进度轮询时序图', 6.2)
body('调度器的主循环遵循四条规则：')
body('① 续跑不重不漏：每批通过 LEFT JOIN 反连接查询“尚无分析结果的评论”（selectPendingComments），只处理剩余数据；analysis_result 上的唯一索引 uk_task_comment(task_id, comment_id) 保证重复写入被数据库拒绝，因此失败重试后进度仍能收敛到 100%。')
body('② 短事务：批量推理与关键词提取在事务外执行，只有“写 analysis_result + 原子累加 analysis_task 进度”放在同一个短事务中提交；避免万行级长事务占用连接与锁。')
body('③ 可终止：取消请求只置位 cancelRequestedTaskIds，在当前批次写完后检查并置为 CANCELED，保证已提交批次的数据一致性；已完成的部分结果保留。')
body('④ 异常隔离：单条样本异常由推理层兜底并计入 error_count；任务级异常由最外层 catch 置为 FAILED，不影响其他任务。')
body('主循环伪代码如下：')
code_block([
    'run(taskId):',
    '  if (!runningTaskIds.add(taskId)) return;',
    '  task = taskMapper.selectById(taskId);',
    '  if (task == null || SUCCESS.equals(task.status)) return;',
    '  if (!inferenceService.isAvailable()) { markFailed(taskId, "模型不可用"); return; }',
    '  markRunning(taskId);',
    '  while (true) {',
    '    pending = commentMapper.selectPendingComments(taskId, batchSize);',
    '    if (pending.isEmpty()) break;',
    '    outcome = processBatch(taskId, pending);',
    '    if (outcome.processed == 0) break;',
    '    if (cancelRequested.contains(taskId)) { markCanceled(taskId); return; }',
    '  }',
    '  finishSuccess(taskId);   // 统计 + 热词 + status=SUCCESS，同一事务',
], size=8.4)
body('任务收尾在一个事务内完成三件事：基于 analysis_result 的聚合 SQL 写入 task_statistics；先删后插写入 keyword_statistics（保证重试幂等）；把任务状态置为 SUCCESS 并记录 finish_time。若任一步失败，事务回滚，任务由外层置为 FAILED，已写入的明细结果保留，可再次重试。')

body('（4）结果查询、统计与导出。', indent=True)
body('结果查询按 taskId、sentiment、keyword 组合筛选，分页大小上限 200；关键词搜索同时匹配 analysis_result.keywords 与 comment_data.content，使用 MyBatis-Plus 的 {0} 占位符绑定参数，避免 SQL 注入。统计接口优先读取 task_statistics 的预聚合结果，把“扫描万行明细做 GROUP BY”降级为“读取 1 行”；若任务被终止或属于历史数据而无统计行，则回退到实时聚合 SQL。导出接口先校验任务存在与数据量不超过 200 000 行，再写响应头，随后按 LIMIT/OFFSET 每 2 000 条分批查询并用 EasyExcel 流式写入，避免一次性加载全部结果。')

h3('3.3 接口设计规范（API Design）')
body('系统对外提供 15 个 RESTful 接口，路径以资源为中心，使用 GET/POST/DELETE 表达查询、创建与删除；请求与响应均为 JSON（上传为 multipart/form-data，导出为 xlsx 字节流）。所有 JSON 响应统一为三段式结构，字段定义如表 3-2 所示。')
caption('表 3-2  统一响应结构')
table(['字段', '类型', '说明'], [
    ['code', 'Integer', '业务状态码，0 表示成功，非 0 表示失败；具体取值见表 3-4'],
    ['message', 'String', '提示信息；失败时为可直接展示给用户的中文文案'],
    ['data', 'T', '业务数据体；失败时为 null；分页数据使用 PageVO 包装'],
], [3.0, 3.0, 9.8], size=8.5)
body('分页请求参数固定为 pageNum（从 1 开始，缺省 1）与 pageSize（缺省 10，上限 200）；分页响应 PageVO 包含 total、pageNum、pageSize、pages、list 五个字段。HTTP 状态码与业务语义对齐：未登录 401、参数错误 400、上传超限 413、唯一键冲突 409、系统异常 500；普通业务错误（如任务状态不允许）仍返回 200，由响应体 code 表达。')
body('接口清单如表 3-3 所示。')
caption('表 3-3  接口清单表')
table(['编号', '接口名称', '方法与路径', '请求参数', '响应数据', '主要错误码'], [
    ['API-01', '注册管理员', 'POST /api/user/register', 'JSON：username、password', 'LoginVO{userId, username}', '400、500'],
    ['API-02', '登录', 'POST /api/user/login', 'JSON：username、password', 'LoginVO{userId, username}', '400、1001'],
    ['API-03', '查询当前用户', 'GET /api/user/me', '无（依赖 Cookie）', 'LoginVO', '401'],
    ['API-04', '退出登录', 'POST /api/user/logout', '无', 'Result<Void>', '401'],
    ['API-05', '上传并解析评论文件', 'POST /api/file/upload', 'multipart：file', 'ParseReportVO', '2001～2006、413、500'],
    ['API-06', '任务分页列表', 'GET /api/task/list', 'pageNum、pageSize、status、keyword', 'PageVO<AnalysisTask>', '500'],
    ['API-07', '任务详情', 'GET /api/task/{id}', '路径 id', 'AnalysisTask', '3002'],
    ['API-08', '删除任务', 'DELETE /api/task/{id}', '路径 id', 'Result<Void>', '3002、3003'],
    ['API-09', '启动 / 重试分析', 'POST /api/task/{id}/run', '路径 id', 'Result<Void>', '3002、3006、500'],
    ['API-10', '查询任务进度', 'GET /api/task/{id}/progress', '路径 id', 'ProgressVO', '3002'],
    ['API-11', '终止任务', 'POST /api/task/{id}/cancel', '路径 id', 'Result<Void>', '3002、3007'],
    ['API-12', '结果明细分页', 'GET /api/result/list', 'pageNum、pageSize、taskId、sentiment、keyword', 'PageVO<ResultVO>', '3002'],
    ['API-13', '情感分布统计', 'GET /api/result/statistics/{taskId}', '路径 taskId', 'SentimentStatisticsVO', '3002、400'],
    ['API-14', '热点关键词', 'GET /api/result/keywords/{taskId}', 'taskId、sentiment、topN', 'List<KeywordVO>', '3002'],
    ['API-15', '导出分析结果', 'GET /api/result/export/{taskId}', '路径 taskId', 'xlsx 字节流', '3002、4001、4002'],
], [1.2, 2.5, 3.9, 3.3, 3.1, 1.8], size=7.4)
body('所有 /api/** 接口（登录、注册除外）都要求有效会话；会话校验由 AuthInterceptor 统一完成，业务代码不感知登录态。错误码按业务域分段：1000 段为账号与会话，2000 段为文件与解析，3000 段为任务与模型，4000 段为导出。完整错误码如表 3-4 所示。')
caption('表 3-4  业务错误码表')
table(['错误码', '含义', '典型触发场景'], [
    ['0', '成功', '请求正常完成'],
    ['400', '请求参数错误', '@Valid 校验失败、路径参数为空、请求体非法 JSON'],
    ['401', '未登录或会话过期', '缺少会话或会话超时'],
    ['404', '资源不存在', '访问不存在的路径'],
    ['500', '系统内部错误', '未预期异常、数据库访问异常'],
    ['1001', '账号或密码错误', '登录失败；账号不存在与密码错误共用'],
    ['1002', '会话已过期', '前端收到后跳转登录页'],
    ['1003', '原密码不正确', '预留的密码修改场景'],
    ['1004', '新密码不符合规则', '密码长度少于 6 位'],
    ['2001', '文件格式不支持', '扩展名不属于 xlsx/xls/csv'],
    ['2002', '文件超过 50 MB', '上传文件大小超限'],
    ['2003', '表头缺失或为空', '文件内容为空或未解析到有效行'],
    ['2004', '未解析到有效评论', '所有行清洗后均为空'],
    ['2005', '文件编码无法识别', 'CSV 既非 UTF-8 也非 GBK 可解码文本'],
    ['2006', '评论列识别失败', '无法从表头或文本长度推断评论列'],
    ['3001', '智能模型不可用', '模型文件缺失或加载失败'],
    ['3002', '任务不存在或已删除', 'taskId 查不到或已逻辑删除'],
    ['3003', '任务状态不允许该操作', '删除执行中的任务'],
    ['3004', '分析执行失败', '推理过程抛出未恢复异常'],
    ['3005', '结果数据不完整', '任务被终止、统计行缺失时提示'],
    ['3006', '任务不可重新分析', '对已完成或执行中的任务点击重跑'],
    ['3007', '任务不可终止', '对非执行中的任务点击终止'],
    ['4001', '导出失败', '写 Excel 时发生 IO 异常'],
    ['4002', '导出数据量过大', '结果行数超过 200 000'],
], [2.0, 6.2, 7.6], size=8)

h3('3.4 数据库详细设计')

body('（1）物理数据模型。', indent=True)
body('数据库为 MySQL 8.0，库名 comment_analysis，字符集 utf8mb4。系统共 6 张表：sys_user（用户）、analysis_task（分析任务，同时承载上传文件元信息）、comment_data（评论原文）、analysis_result（逐条分析结果）、task_statistics（任务级统计）、keyword_statistics（任务级热词）。表间关系如图 3-5 所示。')
figure('dd_er.png', '图 3-5  物理数据模型（E-R 图）', 6.2)
body('外键关系：analysis_task.user_id → sys_user.user_id；comment_data.task_id → analysis_task.task_id；analysis_result.task_id、comment_id 分别指向 analysis_task 与 comment_data；task_statistics.task_id 与 keyword_statistics.task_id 指向 analysis_task。所有外键均设置 ON DELETE CASCADE，删除任务时级联清理子表数据。')

body('（2）数据表结构定义。', indent=True)
body('用户表 sys_user 用于保存管理员账号，单用户模式下仅保留一条记录，密码以 BCrypt 哈希存储。结构如表 3-5 所示。')
caption('表 3-5  sys_user 表结构')
table(['字段名', '数据类型', '长度', '允许空', '键/索引', '默认值', '字段说明'], [
    ['user_id', 'BIGINT', '20', 'N', 'PK，自增', '—', '用户编号'],
    ['username', 'VARCHAR', '50', 'N', 'UK', '—', '登录账号，全局唯一'],
    ['password_hash', 'VARCHAR', '100', 'N', '—', '—', 'BCrypt 哈希后的密码'],
    ['salt', 'VARCHAR', '32', 'N', '—', "''", '盐值；BCrypt 模式留空'],
    ['status', 'TINYINT', '1', 'N', '—', '1', '账号状态：1 启用 / 0 停用'],
    ['last_login_time', 'DATETIME', '—', 'Y', '—', 'NULL', '最近一次登录成功时间'],
    ['create_time', 'DATETIME', '—', 'N', '—', 'CURRENT_TIMESTAMP', '创建时间'],
    ['update_time', 'DATETIME', '—', 'N', '—', 'CURRENT_TIMESTAMP', '更新时间'],
], [3.0, 2.3, 1.2, 1.2, 2.4, 2.3, 3.4], size=7.8)
body('分析任务表 analysis_task 是全系统的核心表，同时保存上传文件信息、执行进度、状态与逻辑删除标记。结构如表 3-6 所示。')
caption('表 3-6  analysis_task 表结构')
table(['字段名', '数据类型', '长度', '允许空', '键/索引', '默认值', '字段说明'], [
    ['task_id', 'BIGINT', '20', 'N', 'PK，自增', '—', '任务编号'],
    ['task_name', 'VARCHAR', '100', 'N', 'IDX', '—', '任务名称，默认取文件名去扩展名'],
    ['file_name', 'VARCHAR', '255', 'N', '—', '—', '上传文件原始名称'],
    ['file_size', 'BIGINT', '20', 'N', '—', '0', '文件大小（字节）'],
    ['user_id', 'BIGINT', '20', 'N', 'FK', '—', '创建人，关联 sys_user'],
    ['model_version', 'VARCHAR', '64', 'N', '—', '—', '本次任务使用的模型版本'],
    ['total_count', 'INT', '11', 'N', '—', '0', '解析入库的评论总数'],
    ['processed_count', 'INT', '11', 'N', '—', '0', '已完成推理条数'],
    ['error_count', 'INT', '11', 'N', '—', '0', '推理异常条数'],
    ['batch_size', 'INT', '11', 'N', '—', '32', '创建任务时的批量大小快照'],
    ['status', 'VARCHAR', '16', 'N', 'IDX', 'PENDING', 'PENDING/RUNNING/SUCCESS/FAILED/CANCELED'],
    ['start_time', 'DATETIME', '—', 'Y', '—', 'NULL', '开始执行时间'],
    ['finish_time', 'DATETIME', '—', 'Y', '—', 'NULL', '结束时间'],
    ['create_time', 'DATETIME', '—', 'N', 'IDX', 'CURRENT_TIMESTAMP', '创建时间'],
    ['update_time', 'DATETIME', '—', 'N', '—', 'CURRENT_TIMESTAMP', '更新时间'],
    ['is_deleted', 'TINYINT', '1', 'N', '—', '0', '逻辑删除：0 未删除 / 1 已删除'],
], [3.0, 2.3, 1.2, 1.2, 2.2, 2.5, 3.4], size=7.8)
body('评论原文表 comment_data 保存清洗后的评论文本，是推理任务的输入源。结构如表 3-7 所示。')
caption('表 3-7  comment_data 表结构')
table(['字段名', '数据类型', '长度', '允许空', '键/索引', '默认值', '字段说明'], [
    ['comment_id', 'BIGINT', '20', 'N', 'PK，自增', '—', '评论编号'],
    ['task_id', 'BIGINT', '20', 'N', 'FK，IDX', '—', '所属任务'],
    ['content', 'VARCHAR', '512', 'N', '—', '—', '清洗后的评论原文'],
    ['row_no', 'INT', '11', 'N', '—', '—', '源文件物理行号'],
    ['create_time', 'DATETIME', '—', 'N', '—', 'CURRENT_TIMESTAMP', '入库时间'],
], [3.0, 2.3, 1.2, 1.2, 2.4, 2.4, 3.3], size=7.8)
body('分析结果表 analysis_result 每条评论一行，保存情感标签、置信度、关键词、复核标记与推理耗时。结构如表 3-8 所示。')
caption('表 3-8  analysis_result 表结构')
table(['字段名', '数据类型', '长度', '允许空', '键/索引', '默认值', '字段说明'], [
    ['result_id', 'BIGINT', '20', 'N', 'PK，自增', '—', '结果编号'],
    ['task_id', 'BIGINT', '20', 'N', 'FK，UK(task,comment)', '—', '任务编号（冗余）'],
    ['comment_id', 'BIGINT', '20', 'N', 'FK，UK(task,comment)', '—', '评论编号'],
    ['sentiment', 'VARCHAR', '16', 'N', 'IDX', '—', 'POSITIVE / NEGATIVE / NEUTRAL'],
    ['confidence', 'DECIMAL', '6,4', 'N', '—', '—', '最大类别概率，[0,1]'],
    ['keywords', 'VARCHAR', '255', 'Y', '—', 'NULL', '该条评论关键词，逗号分隔'],
    ['need_review', 'TINYINT', '1', 'N', '—', '0', '置信度低于阈值时置 1'],
    ['infer_time_ms', 'INT', '11', 'N', '—', '0', '单条推理耗时（毫秒）'],
    ['create_time', 'DATETIME', '—', 'N', '—', 'CURRENT_TIMESTAMP', '写入时间'],
], [3.0, 2.3, 1.2, 1.2, 2.8, 2.1, 3.2], size=7.8)
body('任务统计表 task_statistics 与任务一对一，保存预聚合结果，避免每次打开页面都扫描明细。结构如表 3-9 所示。')
caption('表 3-9  task_statistics 表结构')
table(['字段名', '数据类型', '长度', '允许空', '键/索引', '默认值', '字段说明'], [
    ['stat_id', 'BIGINT', '20', 'N', 'PK，自增', '—', '统计编号'],
    ['task_id', 'BIGINT', '20', 'N', 'FK，UK', '—', '任务编号，一任务一条'],
    ['total_count', 'INT', '11', 'N', '—', '0', '参与统计的评论总数'],
    ['positive_count', 'INT', '11', 'N', '—', '0', '正面条数'],
    ['negative_count', 'INT', '11', 'N', '—', '0', '负面条数'],
    ['neutral_count', 'INT', '11', 'N', '—', '0', '中性条数'],
    ['review_count', 'INT', '11', 'N', '—', '0', '待人工复核条数'],
    ['error_count', 'INT', '11', 'N', '—', '0', '推理异常条数'],
    ['avg_confidence', 'DECIMAL', '6,4', 'Y', '—', 'NULL', '平均置信度'],
    ['total_infer_time_ms', 'BIGINT', '20', 'N', '—', '0', '推理总耗时（毫秒）'],
    ['create_time', 'DATETIME', '—', 'N', '—', 'CURRENT_TIMESTAMP', '生成时间'],
    ['update_time', 'DATETIME', '—', 'N', '—', 'CURRENT_TIMESTAMP', '更新时间'],
], [3.0, 2.3, 1.2, 1.2, 2.2, 2.5, 3.4], size=7.8)
body('关键词统计表 keyword_statistics 保存任务级热词与 TF-IDF 权重，通过 sentiment 区分全局（ALL）与分情感维度。结构如表 3-10 所示。')
caption('表 3-10  keyword_statistics 表结构')
table(['字段名', '数据类型', '长度', '允许空', '键/索引', '默认值', '字段说明'], [
    ['keyword_id', 'BIGINT', '20', 'N', 'PK，自增', '—', '关键词编号'],
    ['task_id', 'BIGINT', '20', 'N', 'FK，UK(task,word,sentiment)', '—', '所属任务'],
    ['word', 'VARCHAR', '64', 'N', 'UK(task,word,sentiment)', '—', '关键词'],
    ['weight', 'DECIMAL', '8,4', 'N', 'IDX(task,weight)', '—', 'TF-IDF 权重'],
    ['word_count', 'INT', '11', 'N', '—', '0', '词频'],
    ['sentiment', 'VARCHAR', '16', 'N', 'UK(task,word,sentiment)', 'ALL', 'ALL / POSITIVE / NEGATIVE / NEUTRAL'],
    ['create_time', 'DATETIME', '—', 'N', '—', 'CURRENT_TIMESTAMP', '生成时间'],
], [3.0, 2.3, 1.2, 1.2, 3.4, 1.9, 2.8], size=7.8)

body('（3）索引与约束设计。', indent=True)
body('索引围绕三类高频访问设计：任务列表按状态与创建时间排序、结果明细按任务与情感筛选、热词按任务与权重降序输出。主要索引与约束如表 3-11 所示。')
caption('表 3-11  索引与约束设计')
table(['名称', '所属表', '字段', '类型', '设计目的'], [
    ['PRIMARY', '全部表', '自增主键', '主键索引', '唯一标识一行'],
    ['uk_username', 'sys_user', 'username', '唯一索引', '保证账号唯一，支撑登录查询'],
    ['uk_task_comment', 'analysis_result', '(task_id, comment_id)', '唯一索引', '同一任务同一评论只写一次，支撑重试幂等'],
    ['uk_task', 'task_statistics', 'task_id', '唯一索引', '保证一任务一条统计'],
    ['uk_task_word_sentiment', 'keyword_statistics', '(task_id, word, sentiment)', '唯一索引', '防止同维度热词重复'],
    ['idx_task_status_create', 'analysis_task', '(status, create_time)', '普通索引', '任务列表按状态筛选并按时间倒序'],
    ['idx_comment_task_row', 'comment_data', '(task_id, row_no)', '普通索引', '按任务顺序读取待处理评论'],
    ['idx_result_task_sentiment', 'analysis_result', '(task_id, sentiment)', '普通索引', '结果明细按情感筛选'],
    ['idx_keyword_task_weight', 'keyword_statistics', '(task_id, weight DESC)', '普通索引', '热词按权重降序直接输出，免排序'],
    ['fk_*', '各子表', 'task_id / user_id / comment_id', '外键', '引用完整性，ON DELETE CASCADE'],
], [3.8, 2.6, 3.8, 1.8, 3.8], size=7.8)
body('（4）设计说明。', indent=True)
body('① 逻辑删除：analysis_task.is_deleted 由 MyBatis-Plus 自动追加 is_deleted = 0，业务查询无需显式处理；物理删除仅用于解析失败后的半成品清理。')
body('② 适度冗余：analysis_result 与 keyword_statistics 冗余 task_id，使结果查询、统计与热词读取不必回连任务表；task_id 在写入时即确定，不存在更新异常。')
body('③ 预聚合：task_statistics 把分组统计从事务查询中剥离，页面读取降为一行；占比字段由应用层按条数/总数计算，不落库，避免冗余不一致。')
body('④ 原子累加：进度使用 UPDATE ... SET processed_count = processed_count + ?，重试续跑不会抹掉历史进度。')
body('⑤ 精度与字符集：置信度、权重使用 DECIMAL，禁止浮点存储；全库 utf8mb4，支持 emoji 与生僻字。')

# ---------------------------------------------------------------------
# 四、智能模块详细设计
# ---------------------------------------------------------------------
h2('四、智能模块（AI/ML）详细设计')

h3('4.1 智能模块工程化封装设计')
body('智能模块不是一个独立脚本，而是系统中的一个可替换组件。封装遵循三条原则：① 业务层只依赖 SentimentInferenceService 接口，不出现 DJL、NDArray、Predictor 等框架类型；② 模型在应用启动时加载一次并常驻，运行期所有推理复用同一 ZooModel 与 Predictor；③ 任何推理异常都在智能层内部兜底，不向业务层抛出，保证分析任务不中断。')
body('ModelRepository 是唯一接触 DJL 的类，使用 @Component 注册为 Spring 单例，在 @PostConstruct 中调用 loadModel()。模型由训练脚本导出为 TorchScript（model.pt），配套 vocab.txt（21 128 个 token）与 labels.txt（POSITIVE、NEGATIVE、NEUTRAL）；加载时通过 Criteria.builder() 指定 PyTorch 引擎、CPU 设备、mapLocation=cpu、training=false，并调用 criteria.loadModel() 与 newPredictor()。模型目录支持文件系统路径与 classpath: 前缀，缺文件时按 app.model.fail-fast 决定阻断启动还是降级。')
body('由于 DJL 的 Predictor 不是线程安全对象，而推理线程池最大可有 4 个线程并发，ModelRepository.predict 在调用 predictor 时使用 synchronized 串行化。CPU 推理本身是串行瓶颈，串行化不会显著降低吞吐，却避免了并发写同一推理器导致的结果错乱。智能模块的类结构如图 4-1 所示。')
figure('dd_ai_class.png', '图 4-1  智能模块类图（ai 包）', 6.2)
body('智能模块各类的职责如表 4-1 所示。')
caption('表 4-1  智能模块类职责')
table(['类/接口', '类型', '职责', '关键实现'], [
    ['SentimentInferenceService', '接口', '业务层可调用的推理门面', '批量推理、关键词提取、可用性检查'],
    ['SentimentInferenceServiceImpl', '实现类', '编排预处理、推理、后处理与降级', 'batchInfer、toResult、extractKeywordsPerText'],
    ['ModelRepository', '组件', '模型单例加载、常驻与释放', '@PostConstruct、loadModel、predict'],
    ['TextPreprocessor', '组件', '推理前文本归一化', '去零宽字符、折叠空白、截断 512 字符'],
    ['BertTokenizer', '组件', 'BERT 中文分词与张量编码', '逐字切分、WordPiece、[CLS]/[SEP]/[PAD]'],
    ['KeywordExtractor', '组件', 'TF-IDF 关键词提取与逐条打标', 'bigram 切分、停用词过滤、tagDocuments'],
    ['KeywordAccumulator', '辅助类', '按批累加词频与文档频率', 'add、topN；只保留聚合结果，避免 OOM'],
    ['SentimentResult / KeywordResult', '数据类', '推理与关键词结果载体', 'label、score、needReview、error；word、weight'],
], [3.6, 2.2, 5.0, 5.0], size=7.8)

h3('4.2 核心类图/流程图')
body('模型加载发生在应用启动阶段，流程如图 4-2 所示。加载成功后 available = true，并合并 model_info.json 中的 baseModel、accuracy、macroF1、exportTime 等元信息；加载失败时默认不阻断启动，而是把 available 置为 false 并记录 ERROR 日志，登录、任务查询、历史结果浏览等不依赖模型的功能仍可使用，调用推理时返回错误码 3001。')
figure('dd_model_load.png', '图 4-2  模型加载与降级流程图', 5.9)
body('批量推理流程如图 4-3 所示。关键设计是“结果下标严格对齐”：先为每条输入填入兜底结果，再只把非空文本送入模型，最后按下标回填；这样即使部分文本为空或单条推理失败，返回列表的长度与顺序仍与输入完全一致，调度层可以安全地按下标组装 analysis_result。')
figure('dd_infer_flow.png', '图 4-3  批量情感推理流程图', 6.2)
body('推理服务的核心实现如下（节选）：')
code_block([
    'public List<SentimentResult> batchInfer(List<String> texts) {',
    '    List<String> cleaned = textPreprocessor.cleanBatch(texts);',
    '    List<SentimentResult> results = new ArrayList<>();',
    '    for (int i = 0; i < cleaned.size(); i++)',
    '        results.add(SentimentResult.fallback(false));',
    '    List<Integer> indexes = new ArrayList<>();',
    '    List<String> pending = new ArrayList<>();',
    '    for (int i = 0; i < cleaned.size(); i++)',
    '        if (!textPreprocessor.isBlank(cleaned.get(i))) {',
    '            indexes.add(i); pending.add(cleaned.get(i));',
    '        }',
    '    if (pending.isEmpty()) return results;',
    '    if (!modelRepository.isAvailable()) {',
    '        markAllFallback(results, indexes, true); return results;',
    '    }',
    '    try {',
    '        float[][] probabilities = modelRepository.predict(pending);',
    '        for (int i = 0; i < indexes.size(); i++)',
    '            results.set(indexes.get(i),',
    '                toResult(probabilities[i], labels, threshold, perItemMs));',
    '    } catch (Exception e) {  // 批次失败后逐条重试，隔离单条异常',
    '        for (Integer index : indexes) retryOne(cleaned.get(index), results, index);',
    '    }',
    '    return results;',
    '}',
], size=8.0)

h3('4.3 模型接口定义')
body('业务层可调用的智能接口共 7 个，签名与输入输出如表 4-2 所示。所有接口均在应用内以 Java 方法调用，不暴露为公网 HTTP 端点，满足“评论数据不外发”的安全约束。')
caption('表 4-2  智能模块接口定义')
table(['方法签名', '输入', '输出', '异常/降级'], [
    ['isAvailable(): boolean', '无', '模型已加载且 Predictor、Tokenizer 非空', '不抛异常'],
    ['getModelInfo(): ModelInfoVO', '无', '版本、设备、标签、maxLength、format、准确率', '模型不可用时 available=false'],
    ['infer(String text): SentimentResult', '单条文本', '标签、置信度、复核标记、耗时', '空文本返回兜底结果'],
    ['batchInfer(List<String>): List<SentimentResult>', '文本列表（与结果同序）', '结果列表，长度与输入一致', '批量失败转逐条；单条失败置 error=true'],
    ['extractKeywords(List<String>, int topN)', '文本列表、TopN', 'List<KeywordResult>', '失败返回空列表'],
    ['extractKeywordsPerText(List<String>, int max)', '文本列表、单条上限', '与输入等长的关键词串列表', '失败返回等长空串列表'],
    ['createKeywordAccumulator()', '无', 'KeywordAccumulator', '不抛异常'],
], [6.0, 3.0, 3.8, 3.0], size=7.8)
body('模型输入为三组形状 [B, 128] 的 int64 张量：input_ids 为词表编号，attention_mask 标记有效 token（1）与补齐位（0），token_type_ids 在本单句任务中全为 0。编码规则与 HuggingFace BertTokenizer（do_lower_case=true）一致：中文逐字切分、空白与标点切分、小写化、WordPiece 最长匹配、添加 [CLS] 与 [SEP]、按 maxLength=128 截断并补齐。补齐为固定长度而非批内动态长度，是为了与 TorchScript 导出时的 dummy 输入形状一致，避免追踪图对动态序列长度产生不确定行为。')
body('模型输出为 [B, 3] 的 logits，后端在 ModelRepository 中执行 softmax(1) 得到三类概率，再取最大概率类别作为标签；标签顺序由 labels.txt 决定，依次为 POSITIVE、NEGATIVE、NEUTRAL。单条结果的 JSON/对象结构如下：')
code_block([
    '{ "label": "POSITIVE", "score": 0.9312, "needReview": false,',
    '  "inferTimeMs": 42.6, "error": false }',
    '// 兜底结果：{ "label": "NEUTRAL", "score": 0.0, "needReview": true,',
    '//             "inferTimeMs": 0.0, "error": true }',
    '// 关键词：{ "word": "售后", "weight": 0.0186, "wordCount": 37 }',
], size=8.2)
body('推理参数集中配置在 application.yml 的 app.inference 与 app.model 下，如表 4-3 所示。参数变更不需要修改代码，重启后生效。')
caption('表 4-3  推理与模型参数')
table(['配置项', '默认值', '含义', '设计要求'], [
    ['app.model.path', 'D:/models/bert-zh-sentiment-v1', '模型目录（纯 ASCII 路径）', 'libtorch 不支持中文路径'],
    ['app.model.max-length', '128', '单条文本最大 token 数', '须与训练/导出时一致'],
    ['app.model.fail-fast', 'false', '加载失败是否阻断启动', '默认降级，保证其余业务可用'],
    ['app.inference.batch-size', '32', '每批推理条数（1～256）', '平衡 CPU 吞吐与内存'],
    ['app.inference.review-threshold', '0.60', '低置信度复核阈值', 'score < 阈值时 need_review = 1'],
    ['app.inference.keyword-top-n', '50', '热点词返回上限', '词云与排名的数据源'],
    ['app.inference.max-text-length', '512', '单条评论最大字符数', '超出截断，防止异常长文本'],
    ['app.inference.keywords-per-comment', '5', '单条评论关键词上限', '写入 analysis_result.keywords'],
], [4.8, 4.2, 3.8, 3.0], size=7.8)
body('关键词提取采用“中文二元组（bigram）滑动窗口 + 英数字整词”的近似切分（JVM 侧不引入 jieba），过滤停用词、单字、纯数字与纯标点后，按 TF-IDF 计算权重：tf = 词频 / 总词数，idf = ln(总评论数 / (含该词的评论数 + 1)) + 1，weight = tf × idf。任务级热词通过 KeywordAccumulator 按批累加词频与文档频率，只保留聚合结果，不缓存全部评论文本，从而让内存占用与文件行数解耦。')

h3('4.4 异常处理与边界条件设计')
body('智能模块的异常处理遵循“内部兜底、外部友好”的原则：底层异常不直接抛给前端，统一转换为 SentimentResult 的兜底值（NEUTRAL、score=0、needReview=true、error=true），由调度层计入 error_count；只有模型整体不可用等无法继续的场景才返回业务错误码 3001。主要异常场景与处理策略如表 4-4 所示。')
caption('表 4-4  异常与边界条件处理')
table(['场景', '触发条件', '处理策略', '对业务层的结果'], [
    ['空文本', 'null、空白、仅零宽字符', '不送模型，返回 fallback(false)', '标签 NEUTRAL、待复核，不计入 error_count'],
    ['超长文本', '字符数 > 512 或 token > 128', '预处理截断到 512 字符，分词按 128 截断', '正常推理，不报错'],
    ['模型不可用', '文件缺失、加载失败、Predictor 为空', '整批返回 fallback(true)，记录 ERROR 日志', '任务置 FAILED 或样本计入 error_count'],
    ['批量推理异常', '单批前向抛出异常', '回退为逐条推理，隔离单条异常', '失败样本兜底，其余正常'],
    ['单条推理异常', '某条样本编码或前向失败', '该条置 fallback(true)，继续后续样本', 'error_count + 1，任务不中断'],
    ['低置信度', 'score < 0.60', '标签保留模型判定值，need_review = 1', '前端显著标注，支持人工复核'],
    ['文件编码异常', 'CSV 非 UTF-8/GBK 可解码', '抛出 BizException(2005)', '提示另存为 UTF-8 后重试'],
    ['评论列无法识别', '表头与文本长度均无法推断', '抛出 BizException(2006)', '提示手工整理评论列'],
    ['数据类型错误', '上传非 xlsx/xls/csv 文件', '抛出 BizException(2001)', '前端提示支持格式'],
    ['空文件/无有效评论', '解析后 validCount = 0', '抛出 BizException(2003/2004)', '清理半成品任务'],
], [3.4, 4.4, 5.0, 3.0], size=7.8)
body('边界设计还包括：模型文件缺失时应用仍可启动，登录与历史结果浏览不受影响；推理线程池队列满时 submitAsync 返回 false，接口提示“系统繁忙，请稍后重试”，任务保持 PENDING，用户可稍后重试；任务被终止时已完成部分结果保留，统计接口对缺失的预聚合行回退到实时聚合。')

# ---------------------------------------------------------------------
# 五、前端界面详细设计
# ---------------------------------------------------------------------
h2('五、前端界面详细设计')

h3('5.1 页面组件划分')
body('前端为原生 HTML5 + CSS3 + JavaScript（ES6）单页应用，不使用 Vue/React 等框架，以减少构建与部署复杂度。页面由两个顶层视图组成：#loginView（登录/注册）与 #appView（分析工作台），通过 hidden 属性切换；全局仅保留一个 #toastHost 轻提示容器。视图与组件结构如图 5-1 所示。')
figure('dd_front_tree.png', '图 5-1  前端视图与组件结构图', 6.2)
body('工作台采用左右两栏布局：左栏 aside.rail 负责上传、任务搜索与任务列表；右栏 main 负责任务信息条、实时进度、统计卡、饼图、词云、热词排名与结果明细表。主要组件的职责如表 5-1 所示。')
caption('表 5-1  前端主要组件职责')
table(['组件', '所属区域', '职责', '关键交互'], [
    ['#authForm', '登录视图', '登录/注册表单，前端校验非空与密码长度', '提交登录、切换注册'],
    ['#dropzone / #fileInput', '左栏', '文件选择与拖拽上传', '点击选择、拖拽释放'],
    ['#uploadMeter', '左栏', '上传阶段真实进度与解析阶段提示', 'XHR upload.onprogress'],
    ['#taskList / #taskPager', '左栏', '任务列表、状态标签与分页', '点击切换任务、按名称搜索'],
    ['#taskbar', '右栏', '任务名称、元信息、状态与操作按钮', '重跑、终止、删除（二次确认）'],
    ['#runBar', '右栏', '分析进度条与已处理/总数', '1.5 秒轮询进度接口'],
    ['#stats / #metrics', '右栏', '三类情感计数、占比、平均置信度、复核与异常数', '随统计接口刷新'],
    ['#pieChart', '右栏', '情感分布饼图', 'ECharts 渲染，语义色区分情感'],
    ['#cloudChart / #rankList', '右栏', '热点词云与 TF-IDF 排名', '全部/正面/负面/中性切换'],
    ['#resultTable / #pager', '右栏', '结果明细、情感筛选、关键词搜索与分页', '筛选、搜索、翻页'],
    ['#exportBtn', '右栏', '导出当前任务结果为 xlsx', '下载并提示文件名'],
], [4.4, 2.6, 5.2, 3.6], size=7.8)

h3('5.2 前后端交互逻辑')
body('前端与后端的交互统一收敛在 api.js：request() 负责 JSON 请求与统一响应拆包，upload() 使用 XMLHttpRequest 以获得上传阶段的真实进度，download() 在导出时先判断 Content-Type，避免把错误 JSON 写成 xlsx 文件。页面交互时序如图 5-2 所示。')
figure('dd_front_seq.png', '图 5-2  前端交互时序图', 6.2)
body('关键调用时机如下：')
body('① 页面初始化：调用 GET /api/user/me 校验会话；成功则加载任务列表，失败则显示登录视图。')
body('② 登录/注册：提交后写入服务端会话，前端不保存 token；后续请求依赖浏览器自动携带的 JSESSIONID。')
body('③ 文件上传：选择或拖拽文件后先在前端校验扩展名与 50 MB 上限，再调用上传接口；上传进度显示在 uploadMeter，解析完成后切换到分析进度。')
body('④ 进度轮询：任务处于 PENDING/RUNNING 时每 1 500 毫秒调用 GET /api/task/{id}/progress；进入终态后停止轮询，刷新任务列表与详情，并提示成功或结束原因。')
body('⑤ 结果加载：选中任务后并发请求 statistics、keywords、list 三个接口，分别渲染统计卡/饼图、词云/排名、明细表；切换情感维度只重新请求关键词接口。')
body('⑥ 异常处理：api.js 遇到 401 或 1002 时触发重新登录；其他错误统一转为 ApiError，由页面用 toast 展示 message，不把后端堆栈暴露给用户。')

h3('5.3 状态管理')
body('前端状态集中在 app.js 顶部的 state 对象中，分为四类：① 用户态 user 与 authMode；② 任务列表 tasks 与 taskQuery（pageNum、pageSize、total、pages）；③ 当前任务 currentTask 与轮询控制 pollTimer、polling、pollTick；④ 结果视图 cloudSentiment、resultQuery 与请求序号 resultSeq、keywordSeq。')
body('状态设计解决了三个具体问题：① 轮询叠加——setInterval 不等待上一次请求，慢网络下会并发堆积；用 polling 标记跳过本轮，保证同一时刻只有一个进度请求。② 过期响应——用户快速切换任务时，旧任务的统计/关键词响应可能晚于新任务返回；每次请求递增 resultSeq/keywordSeq，回调只接受与当前序号一致的响应，避免数据串台。③ 轮询频率与列表新鲜度——每 4 次轮询（约 6 秒）同步一次任务列表，既保持侧栏状态新鲜，又避免每次轮询都触发列表查询。')
body('局部状态（如图表实例、分页控件、表单输入）保留在对应组件或 charts.js 的 instances 缓存中；图表实例复用并在页面销毁时释放，避免重复初始化造成内存泄漏。所有插入 DOM 的评论内容、任务名都经 escapeHtml 转义，防止评论中的特殊字符破坏结构或形成 XSS。')

h3('5.4 交互与可用性设计')
body('① 反馈及时：上传有真实百分比，分析有进度条与已处理条数，任务状态用颜色与文字双重标识；所有请求均有加载态或结果提示。② 防错优先：上传前校验扩展名与大小，删除任务二次确认，终止任务说明“当前批次结束后停止”。③ 空状态友好：无任务时显示引导文案，筛选无结果时提示更换关键词或情感。④ 图表降级：词云插件缺失时自动降级为标签云，ECharts 未加载时不阻塞表格与统计展示。⑤ 可访问性：交互元素使用 button/label 语义、aria-label 与 aria-live，关键信息不只依赖颜色传达。')

# ---------------------------------------------------------------------
# 六、非功能与安全设计
# ---------------------------------------------------------------------
h2('六、非功能与安全设计')

h3('6.1 异常处理机制')
body('系统采用“业务异常 + 全局异常处理器”的统一机制：Service 在业务规则不满足时抛出 BizException（携带 ResultCode），Controller 不写 try-catch；GlobalExceptionHandler 使用 @RestControllerAdvice 捕获各类异常并转换为 Result。异常映射关系如图 6-1 与表 6-1 所示。')
figure('dd_exception.png', '图 6-1  全局异常处理与统一响应机制', 6.2)
caption('表 6-1  异常类型与响应映射')
table(['异常类型', 'HTTP 状态', '业务码', '处理方式'], [
    ['BizException', '200（401 类除外）', '异常携带的码', '记录 warn 日志，返回可展示的中文 message'],
    ['MethodArgumentNotValidException', '400', '400', '取首个字段错误信息返回'],
    ['BindException', '400', '400', '表单参数绑定失败'],
    ['HttpMessageNotReadableException', '400', '400', '请求体不是合法 JSON'],
    ['MaxUploadSizeExceededException', '413', '2002', '上传文件超出限制'],
    ['DuplicateKeyException', '409', '3004', '唯一索引冲突，提示数据重复已跳过'],
    ['DataAccessException', '500', '500', '记录 error 日志，返回系统繁忙'],
    ['Exception（兜底）', '500', '500', '记录完整堆栈，不向前端泄露细节'],
], [5.8, 2.8, 2.4, 4.8], size=7.8)
body('日志策略：业务异常记录 warn（含 code 与 message），系统异常记录 error（含堆栈）；评论原文不写入日志，mapper 包日志级别设为 info，避免 SQL 明细把用户数据落盘。')

h3('6.2 安全性设计')
body('系统为本地单机部署，安全设计集中在账号、会话、输入与数据四个方面，主要措施如表 6-2 所示。')
caption('表 6-2  安全措施')
table(['安全目标', '实现措施', '对应代码/配置'], [
    ['密码不可逆存储', 'BCrypt 加盐慢哈希；历史 SHA-256 登录成功后透明升级', 'UserServiceImpl.passwordEncoder'],
    ['防暴力破解', '同一账号 5 分钟内失败 5 次后锁定 5 分钟；账号不存在与密码错误同提示', 'isLocked / recordFailure'],
    ['会话安全', '服务端 Session，有效期 2 小时；Cookie HttpOnly、SameSite=Lax', 'application.yml、UserController'],
    ['未登录访问拦截', 'AuthInterceptor 拦截 /api/**，登录/注册除外；缺失会话返回 401', 'WebMvcConfig'],
    ['SQL 注入防范', 'MyBatis 参数绑定；关键词搜索使用 {0} 占位符，不拼接字符串', 'ResultServiceImpl、Mapper 注解 SQL'],
    ['XSS 防范', '前端插入评论/任务名统一 escapeHtml 转义', 'app.js'],
    ['上传安全', '白名单扩展名、50 MB 上限、表头与评论列校验、解析失败清理', 'FileServiceImpl'],
    ['数据不外发', '模型本地推理、数据库本地部署，不调用外部 API', 'ModelRepository、application.yml'],
    ['日志隐私', '评论原文不写日志，SQL 明细日志关闭', 'logging.level 配置'],
    ['敏感字段隔离', '实体不直接返回前端，LoginVO 仅含 userId、username', 'vo 包、toLoginVO'],
], [3.4, 8.8, 3.6], size=7.8)
body('需要说明的边界：系统未引入 Spring Security 完整过滤链，仅使用其 BCrypt 实现；会话方案适用于单机单用户，不支持多实例共享会话；接口未做 CSRF Token，依赖 SameSite=Lax 与本地部署场景。若面向公网或多用户，需补充 JWT/集中式会话、RBAC、CSRF 防护与 HTTPS。')

h3('6.3 性能优化设计')
body('性能设计围绕“万级评论、CPU 单机、15 分钟内完成”的目标展开，主要措施如表 6-3 所示。')
caption('表 6-3  性能优化措施')
table(['优化点', '具体做法', '作用'], [
    ['模型常驻', '启动时加载一次，运行期复用 ZooModel 与 Predictor', '避免每次请求重复加载导致延迟与 OOM'],
    ['异步调度', '专用线程池 core=2/max=4/queue=100，AbortPolicy', '上传与查询不被推理阻塞；队列满快速失败'],
    ['批量推理', 'batch-size=32，一次前向处理多条文本', '提高 CPU 利用率，降低单条均摊耗时'],
    ['流式解析', 'EasyExcel 逐行回调，前 200 行缓冲识别列', '内存占用与文件行数无关，支持 50 MB 文件'],
    ['批量写入', '每 1 000 条多值 INSERT，连接串 rewriteBatchedStatements=true', '减少网络往返，提升写入吞吐'],
    ['短事务', '推理与关键词提取在事务外，写结果+进度在同一短事务', '避免万行级长事务占用连接与锁'],
    ['增量词频', 'KeywordAccumulator 只保存词频与文档频率', '不缓存全部评论，避免大文件 OOM'],
    ['预聚合统计', '任务收尾写入 task_statistics，查询读取一行', '把分组统计从查询期移到收尾期'],
    ['原子累加', 'UPDATE processed_count = processed_count + ?', '避免读改写竞争，重试不丢进度'],
    ['索引优化', '任务状态+时间、结果任务+情感、热词任务+权重', '支撑列表、筛选与热词降序'],
    ['分页上限', 'pageSize 上限 200；导出独立 LIMIT/OFFSET', '防止一次拉取过多数据'],
    ['连接池', 'HikariCP min=5、max=20、timeout=30 s', '平衡并发与数据库连接开销'],
], [4.0, 7.6, 4.2], size=7.8)
body('性能边界：单条推理耗时取决于 CPU 与文本长度，系统记录 infer_time_ms 与任务总耗时用于评估；导出上限 200 000 行；单文件上限 50 MB；关键词提取采用 bigram 近似，未引入分词词典，属于质量与依赖之间的折中。')

h3('6.4 可靠性设计')
body('① 重启恢复：TaskRecoveryRunner 在应用启动时把残留的 RUNNING 任务置为 FAILED 并记录 finish_time，使用户可以重试，避免任务永久卡在执行中；恢复失败不阻断启动。② 重试幂等：待处理评论通过反连接查询，已写入结果不会重复处理；uk_task_comment 唯一索引兜底。③ 事务边界：批次写入与进度更新同事务，统计、热词与任务状态同事务，任一步失败整体回滚。④ 优雅停机：推理线程池声明 destroyMethod=shutdown，容器关闭时停止接收新任务。')

# ---------------------------------------------------------------------
# 七、编码规范与工程结构
# ---------------------------------------------------------------------
h2('七、编码规范与工程结构')

h3('7.1 编码规范')
body('后端遵循《阿里巴巴 Java 开发手册》：包名全小写、类名 UpperCamelCase、方法与变量 lowerCamelCase、常量全大写下划线；每个类与公共方法编写 Javadoc，说明职责、参数、返回值与异常；Controller 不写业务逻辑，Service 不直接操作 HttpServletRequest；集合初始化指定容量，避免扩容；异常不使用 e.printStackTrace()，统一走日志框架。源码统一 UTF-8、4 空格缩进，禁止使用制表符。')
body('前端遵循 ES5 兼容写法与 IIFE 模块化，使用 \'use strict\'；函数与关键分支编写 JSDoc；DOM 查询集中在 $() 工具函数；所有动态文本经 escapeHtml 转义；CSS 使用语义化类名与 CSS 变量管理情感色。Python 训练脚本遵循 PEP8，参数通过 argparse 暴露，训练产物与日志写入固定目录。')

h3('7.2 Git 分支管理策略')
body('采用 main / develop / feature / release / hotfix 五类分支：main 只保留可发布版本，禁止直接提交；develop 集成日常开发；feature/<功能> 从 develop 拉出，完成后以 Pull Request 合并回 develop；release 冻结功能只修缺陷，验收通过后合入 main 并回合并 develop；hotfix 从 main 拉出，修复后同时合入 main 与 develop。分支模型如图 7-1 所示。')
figure('dd_git.png', '图 7-1  Git 分支管理策略', 6.0)
body('提交信息遵循 Conventional Commits（feat / fix / docs / refactor / test / chore），便于生成变更记录、定位缺陷引入点与回滚。')

h3('7.3 依赖与构建')
body('后端使用 Maven 构建，继承 spring-boot-starter-parent 2.7.15，编译目标 Java 8，打包为可执行 JAR。核心依赖如表 7-1 所示。')
caption('表 7-1  后端核心依赖')
table(['依赖', '版本', '用途'], [
    ['spring-boot-starter-web', '2.7.15', '内嵌 Tomcat、Spring MVC、Jackson'],
    ['spring-boot-starter-validation', '2.7.15', '@Valid 参数校验'],
    ['mybatis-plus-boot-starter', '3.5.3.1', '通用 CRUD、分页插件、逻辑删除'],
    ['mysql-connector-java', '8.0.33', 'MySQL 8.0 驱动'],
    ['easyexcel', '3.3.4', 'Excel/CSV 流式解析与导出'],
    ['spring-security-crypto', '5.7.x', 'BCrypt 密码哈希（不启用过滤链）'],
    ['djl api / pytorch-engine', '0.38.0', 'Java 端模型加载与推理'],
    ['pytorch-native-cpu', '2.7.1（win-x86_64）', 'CPU 本地库，随包发布'],
    ['lombok', '1.18.34', '编译期生成 getter/setter/构造器'],
    ['spring-boot-starter-actuator', '2.7.15', '健康检查与运行指标'],
    ['commons-compress', '1.25.0', '显式降级，解决 POI 与 DJL 的传递依赖冲突'],
], [5.8, 4.2, 5.8], size=7.8)
body('打包时通过 Maven Profile 切换 PyTorch 本地库：默认 win-x86_64，Linux 使用 -Plinux（linux-x86_64），macOS 使用 -Pmacos（osx-aarch64）。前端静态资源位于 src/main/resources/static，随 JAR 一起发布；模型文件不打入 JAR，部署时复制到纯 ASCII 目录并通过 app.model.path 指定。训练侧依赖 torch、transformers、scikit-learn、pandas、numpy、matplotlib，训练脚本导出 model.pt、vocab.txt、labels.txt、model_info.json 与评估报告。')

# ---------------------------------------------------------------------
# 八、单元测试设计
# ---------------------------------------------------------------------
h2('八、单元测试设计')

h3('8.1 测试策略与范围')
body('单元测试使用 JUnit 5 与 spring-boot-starter-test，执行命令为 mvn test。当前已自动化覆盖智能模块中不依赖 Spring 容器与外部资源的纯逻辑：TextPreprocessor 的文本清洗与截断、KeywordExtractor 的 TF-IDF 提取与增量累加一致性。选择这两部分优先测试的原因是其边界条件多、回归风险高，且无需数据库与模型文件即可稳定运行。')
body('已执行的 5 个用例全部通过（Surefire 报告：KeywordExtractorTest 3 个、TextPreprocessorTest 2 个，Failures 0、Errors 0），用例如表 8-1 所示。')
caption('表 8-1  已执行单元测试用例')
table(['编号', '测试类/方法', '输入数据', '预期结果', '实际结果', '是否通过'], [
    ['TC-AI-01', 'KeywordExtractorTest.extractReturnsKeywordsByTfIdf', '["推荐 推荐 售后 很好", "推荐 售后 服务"]，topN=5', '结果非空；首词为“推荐”；权重>0；条数≤5；词长≥2', '与预期一致', '通过'],
    ['TC-AI-02', 'KeywordExtractorTest.accumulatorMatchesBatchExtract', '同上，分别调用 extract 与累加器 topN(10)', '两者词、权重（误差<0.0001）、词频完全一致', '与预期一致', '通过'],
    ['TC-AI-03', 'KeywordExtractorTest.emptyInputReturnsEmpty', 'null、空列表、未累加的累加器', '返回空列表，不抛异常', '与预期一致', '通过'],
    ['TC-AI-04', 'TextPreprocessorTest.cleanRemovesInvisibleCharactersAndCollapsesWhitespace', '"a\\u200bbc    def"；null', '输出 "abc def"；null 输出空串', '与预期一致', '通过'],
    ['TC-AI-05', 'TextPreprocessorTest.cleanTruncatesToConfiguredLength', 'maxLength=5，"1234567890"', '输出 "12345"', '与预期一致', '通过'],
], [1.4, 4.8, 3.6, 3.4, 1.6, 1.0], size=7.0)
body('针对业务层与接口层，详细设计阶段已定义待补充的测试用例，如表 8-2 所示。这些用例需要数据库、MockMvc 或真实模型文件，计划在集成测试阶段落地。')
caption('表 8-2  待补充测试用例（设计）')
table(['编号', '被测方法/接口', '输入数据', '预期结果', '状态'], [
    ['TC-BIZ-01', 'UserService.login', '正确账号 + 正确密码', '返回 LoginVO；会话写入成功', '待执行'],
    ['TC-BIZ-02', 'UserService.login', '正确账号 + 错误密码，连续 6 次', '前 5 次返回 1001；第 6 次提示 5 分钟后重试', '待执行'],
    ['TC-BIZ-03', 'FileService.uploadAndParse', '扩展名为 .txt 的文件', '抛出 BizException(2001)', '待执行'],
    ['TC-BIZ-04', 'FileService.uploadAndParse', '表头为“评论编号,评论内容”的 CSV', '识别评论列为第 2 列，validCount 正确', '待执行'],
    ['TC-BIZ-05', 'FileService.uploadAndParse', 'GBK 编码的 CSV', '按 GBK 解码，中文不乱码', '待执行'],
    ['TC-BIZ-06', 'AnalysisTaskService.startInference', 'SUCCESS 状态任务', '抛出 BizException(3006)', '待执行'],
    ['TC-BIZ-07', 'InferenceScheduler.run', '执行中请求终止', '当前批次结束后状态为 CANCELED，结果保留', '待执行'],
    ['TC-BIZ-08', 'ResultService.export', '结果行数 200 001', '抛出 BizException(4002)', '待执行'],
    ['TC-AI-06', 'SentimentInferenceService.batchInfer', '含 null、空白、正常文本的混合列表', '结果长度一致；空文本为 NEUTRAL/待复核', '待执行'],
    ['TC-AI-07', 'ModelRepository.predict', '模型目录缺失', 'available=false；调用返回 3001', '待执行'],
], [1.4, 4.4, 4.4, 4.2, 1.4], size=7.2)
body('测试数据设计原则：正常值、边界值、异常值三类成对出现；文本类用例覆盖 null、空串、纯空白、超长、含零宽字符、中英混排；文件类用例覆盖三种扩展名、两种编码、有/无表头、评论列名含“编号”干扰项。')

# ---------------------------------------------------------------------
# 九、实验结论
# ---------------------------------------------------------------------
h2('九、实验结论')

h3('9.1 设计完整性与覆盖度')
body('本详细设计覆盖了《需求规格说明书》中的常规业务与智能模块两部分：常规业务侧，用户管理、文件上传解析、任务调度、结果查询、统计与导出均有对应的类、方法、接口与数据表；智能模块侧，模型加载、文本预处理、分词编码、批量推理、关键词提取与异常降级均有实现级定义。逐项对照概要设计的 7 个模块，本轮落地为 4 个 Controller、4 个 Service 接口及实现、1 个调度器、1 个智能门面与 6 个 Mapper，模块职责与分层约束保持一致。')
body('接口方面，概要设计中的 21 个接口按资源合并为 15 个 RESTful 端点：例如任务列表与历史任务查询合并为 GET /api/task/list（通过 status、keyword 筛选），统计、热词、明细分属三个资源路径；接口数量减少但语义更集中，前端调用路径更短。数据方面，概念模型中的“上传批次”“模型信息”在实现中分别并入 analysis_task 与 model_info.json，最终落地 6 张表，外键与唯一约束完整。')

h3('9.2 编码可行性评估')
body('本文档给出的类名、方法签名、接口路径、请求/响应字段、数据库字段与索引均可直接映射到代码，项目已按此实现并成功编译打包（生成可执行 JAR），AI 纯逻辑单元测试 5/5 通过，说明设计颗粒度满足编码要求。前后端可以按接口契约并行开发：前端只需依赖表 3-3 的路径与字段，后端只需保证统一响应与错误码；智能模块可独立替换实现，不影响业务层。')
body('从评审角度看，设计具备三个可检查的落地条件：① 每个用例都能在类图中找到入口方法；② 每个接口都能在 Controller 中找到对应注解；③ 每个字段都能在实体类与数据字典中找到同名定义。这三点使设计文档可以作为编码完成的验收清单。')

h3('9.3 遗留问题与设计边界')
body('（1）模型效果未达需求目标。当前训练产物 bert-zh-sentiment-v1 基于 uer/chinese_roberta_L-4_H-256 微调，测试集 1 854 条，准确率 67.15%、宏平均 F1 0.6739；其中中性类 F1 仅 0.5928，低置信度（<0.60）样本占 29.77%，与需求提出的“准确率不低于 85%”存在差距。系统层面的应对是把低置信度结果标记为待人工复核，并在界面显著提示；后续需扩充与清洗训练数据、调整类别权重与阈值，或引入更强的预训练模型。该问题属于模型侧遗留，不影响系统链路完整性。')
body('（2）关键词质量为工程折中。JVM 侧未引入 jieba，采用中文二元组滑动窗口近似分词，能覆盖常见双字词，但对三字以上专有名词与跨词边界会产生噪声；后续可接入分词服务或词典，保持接口不变。')
body('（3）单机单用户边界。认证采用服务端 Session，未引入 JWT 与 RBAC；推理为进程内线程池，未引入消息队列；数据库与模型均在本机，未做多实例共享。这些选择符合课程项目与本地部署场景，但不适用于公网多租户或水平扩展。')
body('（4）运行环境约束。模型目录必须为纯 ASCII 路径（libtorch 在 Windows 下无法打开中文路径）；推理仅支持 CPU；上传上限 50 MB、单条文本 512 字符、导出上限 200 000 行。这些约束已在配置与界面提示中体现。')
body('（5）测试覆盖不完整。当前仅对 AI 纯逻辑做了自动化测试，Controller、Service、调度器与导出仍依赖手工验证；后续应补充基于 MockMvc + 测试数据库的集成测试，以及并发提交、取消、重启恢复等可靠性用例。')

# ---------------------------------------------------------------------
# 十、实验心得与体会
# ---------------------------------------------------------------------
h2('十、实验心得与体会')
body('这次详细设计最直接的感受是：从“架构”落到“代码”之间，真正难的不是画类图，而是把边界条件想清楚。概要设计里“文件上传解析”只是一个模块框，细化时才发现它同时牵扯内存、编码、事务和异常清理：最初想把整个上传解析放在一个 @Transactional 里，写完才意识到 50 MB 文件会形成长事务，而且分批提交后一旦失败没有整体回滚。最终改成“流式解析 + 每 1 000 条批量入库 + 失败时物理删除任务并依赖外键级联清理”，并在类图中把 ParseListener 明确为 FileServiceImpl 的内部类，才把“谁负责缓冲、谁负责识别列、谁负责入库”这三件事分开。类图不是装饰，它逼我把这些职责写清楚，否则编码时一定会在一个方法里越写越长。')
body('接口契约的重要性也是在返工中体会到的。前后端由我一个人写，原以为不需要文档，结果在时间字段上先踩了坑：后端 LocalDateTime 序列化出来既可能是字符串也可能是数组，前端一开始直接 new Date() 得到 Invalid Date，只能在 toDate() 里同时兼容两种形式；关键词搜索也出现过“只搜关键词、不搜正文”的偏差，最后统一为同时匹配 keywords 与 comment_data.content。把这些约定写进接口表和统一响应说明之后，页面与接口的联调时间明显缩短。错误码同样如此：2001～2006 把“格式不对、太大、没表头、没解析到、编码不认识、列识别失败”区分开，用户看到的提示才能具体，而不是一句“上传失败”。这让我理解“契约先行”不是形式，而是把可能的歧义提前消灭。')
body('AI 模型工程化的体会更深。模型在 Notebook 里跑通只说明算法可用，把它变成系统组件要解决一堆工程问题：模型必须在启动时只加载一次，否则每次请求都加载会直接拖垮服务；DJL 的 Predictor 不是线程安全的，而线程池最多 4 个线程，只能在调用处串行化；TorchScript 导出时用了固定长度，分词就必须补齐到 128 而不是批内动态补齐；模型只输出 logits，softmax 要放在 Java 侧；批量推理失败还要退化为逐条重试，保证一条坏数据不拖垮整批。最典型的是模型路径：libtorch 在 Windows 下打不开含中文的目录，调试了很久才定位到 errno 2，最后把模型放到纯 ASCII 路径并在配置里写清楚。这些经历让我真正理解“模型不是独立脚本，而是系统的一个组件”——组件要考虑加载、并发、内存、降级和可替换性，业务层只应该看到一个 batchInfer 接口。')
body('还有一点是对“效果”的重新认识。模型集成完成后测试集准确率只有 67.15%，与需求里的 85% 差距明显，中性类尤其弱。起初我想通过调阈值把数字做上去，但那样只会牺牲召回。最后选择在系统层面承认这个边界：保留低置信度标记、提供人工复核入口、在文档中如实记录指标与原因。这让我明白，工程化的诚实比漂亮的数字更重要；详细设计不仅要写“系统怎么跑”，也要写“系统在哪些地方还不够好、下一步怎么改”。')
body('最后是规范与协作。项目虽小，但分层包结构、统一响应、Javadoc、Lombok、Conventional Commits 这些规范让代码始终可读、可查、可回滚；把设计文档当成“给未来自己看的交接材料”，比把它当成作业更有用。下一次再做类似项目，我会更早写接口契约与异常表，更早用单元测试锁住纯逻辑，也会在模型选型阶段就把评估指标和业务阈值对齐，而不是等到集成完才发现效果不达标。')

doc.save(DST)
print('saved:', DST)
print('paragraphs:', len(doc.paragraphs), 'tables:', len(doc.tables), 'figures:', len(doc.inline_shapes))
