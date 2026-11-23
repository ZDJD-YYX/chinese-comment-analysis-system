/**
 * 分析工作台主逻辑。
 *
 * 负责四件事：
 *   1. 登录门禁（后端为单用户模式，登录成功即放行，不涉及令牌）；
 *   2. 任务列表的加载、切换与状态展示；
 *   3. 文件上传 + 解析 + 分析进度轮询；
 *   4. 选中任务后的情感统计、词云、明细表格与导出。
 */
(function () {
  'use strict';

  /* ==========================================================================
     常量与状态
     ========================================================================== */

  /** 任务状态中文文案 */
  var STATUS_LABEL = {
    PENDING: '待执行',
    RUNNING: '分析中',
    SUCCESS: '已完成',
    FAILED: '失败',
    CANCELED: '已终止'
  };

  /** 终态：到达后无需继续轮询 */
  var FINAL_STATUS = ['SUCCESS', 'FAILED', 'CANCELED'];

  /** 任务列表每页条数 */
  var TASK_PAGE_SIZE = 20;

  /** 情感标签语义色，用于复核弹窗的置信度仪表 */
  var SENTIMENT_COLOR = {
    POSITIVE: '#2F9E6B',
    NEGATIVE: '#D9534F',
    NEUTRAL: '#9C8F84'
  };

  /** 进度轮询间隔（毫秒） */
  var POLL_INTERVAL = 1500;

  /** 结果表格候选每页条数 */
  var RESULT_PAGE_SIZE = 20;

  /** 单文件大小上限，与后端 multipart 配置一致 */
  var MAX_FILE_SIZE = 50 * 1024 * 1024;

  var state = {
    user: null,
    /** 当前登录表单模式：login / register */
    authMode: 'login',
    /** 当前视图：workspace / dashboard / settings */
    view: 'workspace',
    /** 最近一次导入的备份文件名，供下载回退使用 */
    reportBackup: null,
    tasks: [],
    /** 任务列表分页状态 */
    taskQuery: { pageNum: 1, pageSize: TASK_PAGE_SIZE, total: 0, pages: 0 },
    currentTask: null,
    /** 轮询定时器 */
    pollTimer: null,
    /** 是否有轮询请求在执行，避免请求叠加 */
    polling: false,
    /** 轮询计数，用于降低任务列表的刷新频率 */
    pollTick: 0,
    /** 智能输入提交中标记，避免重复提交 */
    smartBusy: false,
    /** 当前待确认的网页正文预览与原始链接 */
    pagePreview: null,
    previewUrl: '',
    cloudSentiment: 'ALL',
    /** 结果/关键词/统计/详情请求序号，用于丢弃过期响应 */
    resultSeq: 0,
    keywordSeq: 0,
    trendSeq: 0,
    statSeq: 0,
    detailSeq: 0,
    taskSeq: 0,
    /** 文件上传/解析进行中标记，避免重复创建任务 */
    uploadBusy: false,
    /** 待人工指定评论列的上传报告（含令牌与候选列） */
    pendingColumnReport: null,
    /** 评论列弹窗当前选中的列序号 */
    columnSelection: -1,
    /** 当前页结果行，人工复核弹窗按 resultId 回查 */
    resultRows: [],
    /** 任务批量选择：taskId → true */
    selectedTaskIds: {},
    /** 结果批量选择：resultId → true */
    selectedResultIds: {},
    /** 当前重命名的任务编号 */
    renameTargetId: null,
    /** 当前正在复核的行与人工结论 */
    reviewTarget: null,
    reviewSelection: '',
    /** 低置信度复核阈值，首次打开复核弹窗时从设置接口读取并缓存 */
    reviewThreshold: null,
    /** 结果表格查询条件 */
    resultQuery: {
      pageNum: 1,
      pageSize: RESULT_PAGE_SIZE,
      total: 0,
      pages: 0,
      sentiment: '',
      keyword: '',
      needReview: '',
      reviewed: '',
      sortBy: '',
      sortOrder: ''
    }
  };

  /* ==========================================================================
     工具函数
     ========================================================================== */

  /**
   * 按 id 取元素。
   * @param {string} id 元素 id
   * @returns {HTMLElement} 元素
   */
  function $(id) {
    return document.getElementById(id);
  }

  /**
   * 转义 HTML，避免评论内容、任务名中的特殊字符破坏结构。
   * @param {*} value 原始值
   * @returns {string} 转义后的文本
   */
  function escapeHtml(value) {
    if (value === null || value === undefined) {
      return '';
    }
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  /**
   * 补零。
   * @param {number} num 数字
   * @returns {string} 两位字符串
   */
  function pad(num) {
    return num < 10 ? '0' + num : String(num);
  }

  /**
   * 把后端时间转换为 Date。
   * 兼容 ISO 字符串（2026-09-26T10:30:00）与 Jackson 时间戳数组两种形式。
   * @param {*} value 时间字段
   * @returns {Date|null} 日期对象
   */
  function toDate(value) {
    if (!value) {
      return null;
    }
    if (Array.isArray(value)) {
      return new Date(value[0], (value[1] || 1) - 1, value[2] || 1,
        value[3] || 0, value[4] || 0, value[5] || 0);
    }
    var date = new Date(String(value).replace(' ', 'T'));
    return isNaN(date.getTime()) ? null : date;
  }

  /**
   * 格式化时间。
   * @param {*} value 时间字段
   * @param {boolean} withYear 是否输出年份
   * @returns {string} 展示文案
   */
  function formatTime(value, withYear) {
    var date = toDate(value);
    if (!date) {
      return '—';
    }
    var text = (withYear ? date.getFullYear() + '-' : '')
      + pad(date.getMonth() + 1) + '-' + pad(date.getDate())
      + ' ' + pad(date.getHours()) + ':' + pad(date.getMinutes());
    return text;
  }

  /**
   * 格式化文件大小。
   * @param {number} bytes 字节数
   * @returns {string} 展示文案
   */
  function formatSize(bytes) {
    if (!bytes && bytes !== 0) {
      return '—';
    }
    if (bytes < 1024) {
      return bytes + ' B';
    }
    if (bytes < 1024 * 1024) {
      return (bytes / 1024).toFixed(1) + ' KB';
    }
    return (bytes / 1024 / 1024).toFixed(1) + ' MB';
  }

  /**
   * 数字千分位。
   * @param {number} value 数字
   * @returns {string} 展示文案
   */
  function formatNumber(value) {
    if (value === null || value === undefined || value === '') {
      return '—';
    }
    return Number(value).toLocaleString('zh-CN');
  }

  /**
   * 展示轻提示。
   * @param {string} message 提示文案
   * @param {string} type    ok / err / info
   */
  function toast(message, type) {
    var host = $('toastHost');
    var item = document.createElement('div');
    item.className = 'toast toast--' + (type || 'info');
    item.textContent = message;
    host.appendChild(item);
    setTimeout(function () {
      item.remove();
    }, 3600);
  }

  /**
   * 统一错误提示：登录态失效时回到登录页。
   * @param {Error} error 异常
   */
  function reportError(error) {
    if (api.isUnauthorized(error)) {
      toast(error.message, 'err');
      logout(true);
      return;
    }
    toast((error && error.message) || '操作失败，请稍后重试', 'err');
  }

  /* ==========================================================================
     登录门禁
     ========================================================================== */

  /**
   * 切换登录 / 注册表单形态。
   * @param {string} mode login 或 register
   */
  function setAuthMode(mode) {
    state.authMode = mode;
    var isRegister = mode === 'register';
    $('authTitle').textContent = isRegister ? '注册管理员账号' : '登录工作台';
    $('authSub').textContent = isRegister ? '系统为单用户模式，注册后即可使用' : '使用管理员账号继续';
    $('authSubmit').textContent = isRegister ? '注册并进入' : '进入工作台';
    $('authSwitch').textContent = isRegister ? '已有账号，返回登录' : '还没有账号，注册管理员账号';
    $('authPassword').setAttribute('autocomplete', isRegister ? 'new-password' : 'current-password');
    $('authError').hidden = true;
  }

  /**
   * 展示登录页。
   */
  function showLogin() {
    $('appView').hidden = true;
    $('loginView').hidden = false;
    $('authPassword').value = '';
    setAuthMode('login');
    $('authUsername').focus();
  }

  /**
   * 展示工作台。
   */
  function showApp() {
    $('loginView').hidden = true;
    $('appView').hidden = false;
    renderRailUser();
    setView('workspace', false);
    loadTasks();
  }

  /**
   * 渲染侧边栏底部用户区（账号名 + 头像首字母）。
   */
  function renderRailUser() {
    var username = state.user ? state.user.username : '';
    $('railUser').textContent = username || '未登录';
    $('railAvatar').textContent = username ? username.charAt(0).toUpperCase() : '—';
  }

  /* ==========================================================================
     视图切换
     ========================================================================== */

  /**
   * 按当前视图与选中任务，统一决定各区块的显隐。
   */
  function applyViewVisibility() {
    var workspace = state.view === 'workspace';
    var hasTask = !!state.currentTask;
    $('dashboardView').hidden = state.view !== 'dashboard';
    $('compareView').hidden = state.view !== 'compare';
    $('settingsView').hidden = state.view !== 'settings';
    $('taskbar').hidden = !workspace || !hasTask;
    $('emptyState').hidden = !workspace || hasTask;
    $('taskContent').hidden = !workspace || !hasTask;
  }

  /**
   * 切换视图。
   * @param {string}  view  workspace / dashboard / compare / settings
   * @param {boolean} load  是否立即加载该视图数据
   */
  function setView(view, load) {
    state.view = view;
    $('railNav').querySelectorAll('.rail__nav-btn').forEach(function (button) {
      button.classList.toggle('is-active', button.dataset.view === view);
    });
    applyViewVisibility();
    if (!load) {
      return;
    }
    if (view === 'dashboard') {
      loadDashboard();
    } else if (view === 'compare') {
      loadCompareOptions();
    } else if (view === 'settings') {
      loadSettings();
    } else if (view === 'workspace') {
      // 图表在隐藏状态下无法正确计算尺寸，切回工作台后重新自适应
      requestAnimationFrame(function () {
        charts.resize();
      });
    }
  }

  /**
   * 退出登录（销毁后端会话）。
   * @param {boolean} silent 是否静默（会话失效时使用）
   */
  async function logout(silent) {
    try {
      // 会话已失效时该请求会返回 401，忽略即可
      await api.post('/api/user/logout');
    } catch (e) {
      // 忽略退出接口异常
    }
    closeProfile();
    closeParseReport();
    state.user = null;
    state.tasks = [];
    state.currentTask = null;
    state.taskQuery = { pageNum: 1, pageSize: TASK_PAGE_SIZE, total: 0, pages: 0 };
    stopPolling();
    showLogin();
    if (!silent) {
      toast('已退出登录', 'info');
    }
  }

  /**
   * 处理登录 / 注册提交。
   * @param {Event} event 表单提交事件
   */
  async function handleAuthSubmit(event) {
    event.preventDefault();

    var username = $('authUsername').value.trim();
    var password = $('authPassword').value;
    var isRegister = state.authMode === 'register';
    var errorBox = $('authError');
    var submitBtn = $('authSubmit');

    // 前置校验：与后端 DTO 的约束保持一致，避免无意义的请求
    var tip = '';
    if (!username) {
      tip = '请输入账号';
    } else if (!password) {
      tip = '请输入密码';
    } else if (isRegister && password.length < 6) {
      tip = '密码长度需为 6～64 位';
    }
    if (tip) {
      errorBox.textContent = tip;
      errorBox.hidden = false;
      return;
    }

    errorBox.hidden = true;
    submitBtn.disabled = true;
    submitBtn.textContent = isRegister ? '注册中…' : '登录中…';

    try {
      var path = isRegister ? '/api/user/register' : '/api/user/login';
      var data = await api.post(path, { username: username, password: password });
      state.user = data;
      toast(isRegister ? '注册成功，欢迎使用' : '登录成功', 'ok');
      showApp();
    } catch (error) {
      errorBox.textContent = (error && error.message) || '操作失败，请稍后重试';
      errorBox.hidden = false;
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = isRegister ? '注册并进入' : '进入工作台';
    }
  }

  /* ==========================================================================
     个人中心
     ========================================================================== */

  /**
   * 打开个人中心弹窗，向后端刷新账号信息后渲染。
   */
  async function openProfile() {
    try {
      state.user = await api.get('/api/user/me');
    } catch (error) {
      reportError(error);
      return;
    }
    renderRailUser();
    renderProfile();
    $('profileModal').hidden = false;
    // 打开时光标落在原密码框，方便直接修改密码
    $('oldPassword').focus();
  }

  /**
   * 关闭个人中心弹窗，并清空密码表单与错误提示。
   */
  function closeProfile() {
    var modal = $('profileModal');
    if (!modal || modal.hidden) {
      return;
    }
    modal.hidden = true;
    $('passwordError').hidden = true;
    ['oldPassword', 'newPassword', 'confirmPassword'].forEach(function (id) {
      $(id).value = '';
    });
  }

  /**
   * 渲染个人中心账号信息。
   */
  function renderProfile() {
    var user = state.user || {};
    var username = user.username || '—';
    $('profileName').textContent = username;
    $('profileUsername').textContent = username;
    $('profileAvatar').textContent = username === '—' ? '—' : username.charAt(0).toUpperCase();
    $('profileLastLogin').textContent = formatTime(user.lastLoginTime, true);
    $('profileCreated').textContent = formatTime(user.createTime, true);
  }

  /**
   * 处理修改密码提交。
   * @param {Event} event 表单提交事件
   */
  async function handlePasswordSubmit(event) {
    event.preventDefault();

    var oldPassword = $('oldPassword').value;
    var newPassword = $('newPassword').value;
    var confirmPassword = $('confirmPassword').value;
    var errorBox = $('passwordError');
    var submitBtn = $('passwordSubmit');

    // 前置校验：与后端规则一致，避免无意义的请求
    var tip = '';
    if (!oldPassword) {
      tip = '请输入原密码';
    } else if (!newPassword) {
      tip = '请输入新密码';
    } else if (newPassword.length < 6 || newPassword.length > 64) {
      tip = '新密码长度需为 6～64 位';
    } else if (newPassword !== confirmPassword) {
      tip = '两次输入的新密码不一致';
    }
    if (tip) {
      errorBox.textContent = tip;
      errorBox.hidden = false;
      return;
    }

    errorBox.hidden = true;
    submitBtn.disabled = true;
    submitBtn.textContent = '更新中…';

    try {
      await api.post('/api/user/password', {
        oldPassword: oldPassword,
        newPassword: newPassword
      });
      toast('密码修改成功，请牢记新密码', 'ok');
      closeProfile();
    } catch (error) {
      if (api.isUnauthorized(error)) {
        reportError(error);
        return;
      }
      errorBox.textContent = (error && error.message) || '修改失败，请稍后重试';
      errorBox.hidden = false;
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = '更新密码';
    }
  }

  /* ==========================================================================
     数据看板
     ========================================================================== */

  /** 看板请求序号，用于丢弃过期响应 */
  var dashboardSeq = 0;

  /**
   * 加载看板汇总数据。
   */
  async function loadDashboard() {
    var seq = ++dashboardSeq;
    try {
      var data = await api.get('/api/dashboard/summary');
      if (seq !== dashboardSeq) {
        return;
      }
      renderDashboard(data || {});
    } catch (error) {
      reportError(error);
    }
  }

  /**
   * 渲染看板。
   * @param {object} data 看板汇总
   */
  function renderDashboard(data) {
    $('kpiTasks').textContent = formatNumber(data.totalTasks);
    $('kpiTasksHint').textContent = '已完成 ' + formatNumber(data.successTasks)
      + ' · 执行中 ' + formatNumber(data.runningTasks);
    $('kpiComments').textContent = formatNumber(data.totalComments);
    $('kpiReview').textContent = formatNumber(data.reviewCount);
    $('kpiConfidence').textContent = (data.avgConfidence === null || data.avgConfidence === undefined)
      ? '—'
      : (Number(data.avgConfidence) * 100).toFixed(1) + '%';

    var positive = Number(data.positiveCount || 0);
    var negative = Number(data.negativeCount || 0);
    var neutral = Number(data.neutralCount || 0);
    var total = positive + negative + neutral;
    $('boardTotal').textContent = '共 ' + formatNumber(total) + ' 条评论';
    renderBoardStat('Pos', positive, total);
    renderBoardStat('Neg', negative, total);
    renderBoardStat('Neu', neutral, total);

    charts.renderTrend($('trendChart'), data.trend || []);
    renderRecentTasks(data.recentTasks || []);
    // 看板可见后再自适应尺寸
    requestAnimationFrame(function () {
      charts.resize();
    });
  }

  /**
   * 渲染看板中的单项情感读数。
   * @param {string} key    Pos / Neg / Neu
   * @param {number} count  条数
   * @param {number} total  总条数
   */
  function renderBoardStat(key, count, total) {
    var ratio = total > 0 ? count / total : 0;
    $('board' + key + 'Count').textContent = formatNumber(count);
    $('board' + key + 'Ratio').textContent = (ratio * 100).toFixed(1) + '%';
    $('board' + key + 'Bar').style.width = (ratio * 100).toFixed(2) + '%';
  }

  /**
   * 渲染最近任务列表，点击切换到该任务。
   * @param {Array} tasks 任务摘要
   */
  function renderRecentTasks(tasks) {
    var host = $('boardRecent');
    if (!tasks.length) {
      host.innerHTML = '<p class="board-recent__empty">暂无任务，先到「分析工作台」上传一份评论文件</p>';
      return;
    }
    host.innerHTML = tasks.map(function (task) {
      var status = task.status || 'PENDING';
      return ''
        + '<button class="recent" type="button" data-task-id="' + escapeHtml(task.taskId) + '">'
        + '  <span class="recent__name">' + escapeHtml(task.taskName || ('任务 ' + task.taskId)) + '</span>'
        + '  <span class="recent__meta">' + formatNumber(task.totalCount) + ' 条 · '
        +      escapeHtml(formatTime(task.createTime, true)) + '</span>'
        + '  <span class="pill pill--' + escapeHtml(status) + '">'
        +      escapeHtml(STATUS_LABEL[status] || status) + '</span>'
        + '</button>';
    }).join('');
  }

  /* ==========================================================================
     系统设置
     ========================================================================== */

  /**
   * 加载设置与操作记录。
   */
  async function loadSettings() {
    try {
      var settings = await api.get('/api/settings');
      renderSettings(settings || {});
      await loadAudit();
    } catch (error) {
      reportError(error);
    }
  }

  /**
   * 渲染模型信息与推理参数。
   * @param {object} settings 设置视图
   */
  function renderSettings(settings) {
    var model = settings.model || {};
    var stateLabel = $('modelState');
    stateLabel.textContent = model.available ? '模型运行中' : '模型不可用';
    stateLabel.className = 'card__aside ' + (model.available ? 'state--ok' : 'state--bad');

    var facts = [
      ['系统版本', settings.version || '—'],
      ['模型版本', model.modelVersion || '—'],
      ['推理设备', model.device || '—'],
      ['模型格式', model.format || '—'],
      ['最大 token 数', model.maxLength !== null && model.maxLength !== undefined ? String(model.maxLength) : '—'],
      ['标签顺序', (model.labels && model.labels.length) ? model.labels.join(' / ') : '—'],
      ['基座模型', model.baseModel || '—'],
      ['测试集准确率', model.accuracy !== null && model.accuracy !== undefined
        ? (Number(model.accuracy) * 100).toFixed(2) + '%' : '—'],
      ['宏平均 F1', model.macroF1 !== null && model.macroF1 !== undefined
        ? Number(model.macroF1).toFixed(4) : '—'],
      ['模型导出时间', model.exportTime || '—'],
      ['模型目录', model.modelDir || '—']
    ];
    $('modelFacts').innerHTML = facts.map(function (item) {
      return '<div class="facts__row"><dt>' + escapeHtml(item[0]) + '</dt><dd>'
        + escapeHtml(item[1]) + '</dd></div>';
    }).join('');

    var inference = settings.inference || {};
    $('reviewThreshold').value = inference.reviewThreshold !== undefined ? inference.reviewThreshold : '';
    $('keywordsPerComment').value = inference.keywordsPerComment !== undefined ? inference.keywordsPerComment : '';

    var readonly = [
      ['推理批量大小', String(inference.batchSize !== undefined ? inference.batchSize : '—')],
      ['热点词条数上限', String(inference.keywordTopN !== undefined ? inference.keywordTopN : '—')],
      ['单条最大字符数', String(inference.maxTextLength !== undefined ? inference.maxTextLength : '—')]
    ];
    $('readonlyFacts').innerHTML = '<div class="facts__caption">以下参数影响任务队列，修改需调整配置文件并重启</div>'
      + readonly.map(function (item) {
        return '<div class="facts__row"><dt>' + escapeHtml(item[0]) + '</dt><dd>'
          + escapeHtml(item[1]) + '</dd></div>';
      }).join('');

    $('settingsError').hidden = true;
  }

  /**
   * 保存可调参数。
   * @param {Event} event 表单提交事件
   */
  async function handleSettingsSubmit(event) {
    event.preventDefault();

    var threshold = Number($('reviewThreshold').value);
    var perComment = Number($('keywordsPerComment').value);
    var errorBox = $('settingsError');
    var submit = $('settingsSubmit');

    var tip = '';
    if (!isFinite(threshold) || threshold < 0.5 || threshold > 0.99) {
      tip = '复核阈值需在 0.50～0.99 之间';
    } else if (!isFinite(perComment) || perComment < 1 || perComment > 10
        || Math.round(perComment) !== perComment) {
      tip = '单条关键词数量需为 1～10 的整数';
    }
    if (tip) {
      errorBox.textContent = tip;
      errorBox.hidden = false;
      return;
    }

    errorBox.hidden = true;
    submit.disabled = true;
    submit.textContent = '保存中…';
    try {
      var settings = await api.post('/api/settings', {
        reviewThreshold: threshold,
        keywordsPerComment: perComment
      });
      renderSettings(settings || {});
      // 复核阈值可能已变化，清掉缓存让复核弹窗下次读取最新值
      state.reviewThreshold = null;
      toast('设置已保存，对后续任务生效', 'ok');
      await loadAudit();
    } catch (error) {
      if (api.isUnauthorized(error)) {
        reportError(error);
        return;
      }
      errorBox.textContent = (error && error.message) || '保存失败，请稍后重试';
      errorBox.hidden = false;
    } finally {
      submit.disabled = false;
      submit.textContent = '保存设置';
    }
  }

  /**
   * 加载操作记录。
   */
  async function loadAudit() {
    try {
      var rows = await api.get('/api/settings/audit', { limit: 50 });
      renderAudit(rows || []);
    } catch (error) {
      reportError(error);
    }
  }

  /**
   * 渲染操作记录表。
   * @param {Array} rows 记录列表
   */
  function renderAudit(rows) {
    var body = $('auditBody');
    var empty = $('auditEmpty');
    var table = $('auditTable');
    if (!rows.length) {
      body.innerHTML = '';
      table.hidden = true;
      empty.hidden = false;
      return;
    }
    table.hidden = false;
    empty.hidden = true;
    body.innerHTML = rows.map(function (row) {
      return ''
        + '<tr>'
        + '  <td class="cell-time">' + escapeHtml(row.time || '—') + '</td>'
        + '  <td>' + escapeHtml(row.username || '—') + '</td>'
        + '  <td>' + escapeHtml(row.action || '—') + '</td>'
        + '  <td class="cell-content">' + escapeHtml(row.detail || '—') + '</td>'
        + '</tr>';
    }).join('');
  }

  /* ==========================================================================
     解析报告
     ========================================================================== */

  /**
   * 展示上传后的解析报告（FR-BIZ-10）。
   * @param {object} report   解析报告
   * @param {string} fileName 源文件名（兜底）
   */
  function showParseReport(report, fileName) {
    $('reportFile').textContent = (report.fileName || fileName || '—')
      + ' · ' + formatSize(report.fileSize);
    renderValidation(report.validation);
    $('reportTotal').textContent = formatNumber(report.totalCount);
    $('reportValid').textContent = formatNumber(report.validCount);
    $('reportFiltered').textContent = formatNumber(report.filteredCount);
    $('reportColumn').textContent = (report.commentColumn === null || report.commentColumn === undefined)
      ? '—'
      : '第 ' + (Number(report.commentColumn) + 1) + ' 列';

    var reasons = report.filterReasons || {};
    var keys = Object.keys(reasons);
    if (!keys.length) {
      $('reportReasons').hidden = true;
      $('reportReasonList').innerHTML = '';
    } else {
      $('reportReasons').hidden = false;
      $('reportReasonList').innerHTML = keys.map(function (key) {
        return '<li><span>' + escapeHtml(key) + '</span><b>'
          + formatNumber(reasons[key]) + '</b></li>';
      }).join('');
    }
    $('reportModal').hidden = false;
  }

  /**
   * 关闭解析报告弹窗。
   */
  function closeParseReport() {
    var modal = $('reportModal');
    if (modal && !modal.hidden) {
      modal.hidden = true;
    }
  }

  /** 校验状态文案 */
  var VALIDATION_LABEL = {
    PASS: '校验通过',
    FIXED: '已自动修复',
    WARNING: '需人工关注',
    ERROR: '校验失败'
  };

  /**
   * 渲染导入校验结果（编码、乱码、不可见字符、备份）。
   * @param {object} validation 校验报告
   */
  function renderValidation(validation) {
    var box = $('reportValidation');
    if (!validation) {
      box.hidden = true;
      state.reportBackup = null;
      return;
    }
    box.hidden = false;

    var status = validation.status || 'PASS';
    var badge = $('reportStatus');
    badge.textContent = VALIDATION_LABEL[status] || status;
    badge.className = 'validation__badge validation__badge--' + status.toLowerCase();
    $('reportSummary').textContent = validation.summary || '';

    var format = (validation.actualFormat || '—').toUpperCase();
    if (validation.originalFormat && validation.originalFormat !== validation.actualFormat) {
      format = validation.originalFormat.toUpperCase() + ' → ' + format;
    }
    $('reportFormat').textContent = format;

    var detected = validation.encodingDetected || '—';
    var used = validation.encodingUsed;
    $('reportEncoding').textContent = (used && used !== detected)
      ? detected + ' → ' + used
      : detected;

    var issues = validation.issues || [];
    $('reportIssues').hidden = !issues.length;
    $('reportIssues').innerHTML = issues.map(function (issue) {
      var level = String(issue.level || '').toLowerCase();
      var count = Number(issue.count || 0);
      return ''
        + '<li class="validation__issue validation__issue--' + escapeHtml(level) + '">'
        + '  <span class="validation__issue-type">' + escapeHtml(issue.type || '') + '</span>'
        + '  <span class="validation__issue-detail">' + escapeHtml(issue.detail || '') + '</span>'
        + (count > 0 ? '  <b>' + formatNumber(count) + '</b>' : '')
        + '</li>';
    }).join('');

    var backup = validation.backupFile || '';
    state.reportBackup = backup || null;
    $('reportBackup').textContent = backup
      ? '已保存 · ' + formatSize(validation.backupSize)
      : '未保存';
    $('downloadBackupBtn').hidden = !backup;
  }

  /**
   * 下载本次导入的原始文件备份。
   */
  async function downloadBackup() {
    if (!state.reportBackup) {
      return;
    }
    var button = $('downloadBackupBtn');
    var label = button.textContent;
    button.disabled = true;
    button.textContent = '下载中…';
    try {
      var filename = await api.download('/api/file/backup',
        { name: state.reportBackup }, state.reportBackup);
      toast('已下载备份「' + filename + '」', 'ok');
    } catch (error) {
      reportError(error);
    } finally {
      button.disabled = false;
      button.textContent = label;
    }
  }

  /* ==========================================================================
     任务列表
     ========================================================================== */

  /**
   * 加载任务列表。
   *
   * 支持关键字、创建时间范围组合检索（FR-BIZ-22：时间范围 / 任务状态 / 文件名关键字）。
   */
  async function loadTasks() {
    var keyword = $('taskSearch').value.trim();
    var query = state.taskQuery;
    var seq = ++state.taskSeq;
    try {
      var page = await api.get('/api/task/list', {
        pageNum: query.pageNum,
        pageSize: query.pageSize,
        keyword: keyword,
        status: $('taskStatus').value,
        startTime: $('taskDateStart').value,
        endTime: $('taskDateEnd').value
      });
      // 快速修改搜索条件时，旧请求不能覆盖新结果
      if (seq !== state.taskSeq) {
        return;
      }
      state.tasks = (page && page.list) || [];
      // 选择状态只保留当前页仍存在的任务，避免删除后残留幽灵选择
      var visible = {};
      state.tasks.forEach(function (task) {
        visible[task.taskId] = true;
      });
      Object.keys(state.selectedTaskIds).forEach(function (id) {
        if (!visible[id]) {
          delete state.selectedTaskIds[id];
        }
      });
      query.total = Number((page && page.total) || 0);
      query.pages = Number((page && page.pages) || 0);
      query.pageNum = Number((page && page.pageNum) || query.pageNum);
      // 删除末页最后一条后，当前页可能越界，自动回退
      if (query.pageNum > 1 && query.pages > 0 && query.pageNum > query.pages) {
        query.pageNum = query.pages;
        return loadTasks();
      }
      renderTasks();
      renderTaskPager();
      // 任务全部结束且当前无选中任务时，同步停掉轮询
      if (!state.currentTask && !hasRunningTask()) {
        stopPolling();
      }
    } catch (error) {
      if (seq !== state.taskSeq) {
        return;
      }
      state.tasks = [];
      renderTasks('任务列表加载失败：' + ((error && error.message) || '未知错误'));
      renderTaskPager();
    }
  }

  /**
   * 列表中是否存在未结束的任务。
   * @returns {boolean} 是否存在
   */
  function hasRunningTask() {
    return state.tasks.some(function (task) {
      return FINAL_STATUS.indexOf(task.status) < 0;
    });
  }

  /**
   * 渲染任务列表。
   * @param {string} note 需要展示的提示文案（用于空态或错误态）
   */
  function renderTasks(note) {
    var host = $('taskList');
    $('taskCount').textContent = formatNumber(state.taskQuery.total);
    updateTaskBatchBar();

    if (note) {
      host.innerHTML = '<div class="task-list__note">' + escapeHtml(note) + '</div>';
      return;
    }
    if (!state.tasks.length) {
      host.innerHTML = '<div class="task-list__note">暂无分析任务<br>上传一份评论文件即可创建</div>';
      return;
    }

    var html = state.tasks.map(function (task) {
      var isActive = state.currentTask && state.currentTask.taskId === task.taskId;
      var status = task.status || 'PENDING';
      var total = Number(task.totalCount || 0);
      var processed = Number(task.processedCount || 0);
      var percent = total ? Math.min(100, Math.round((processed / total) * 100)) : 0;
      var showMeter = status === 'RUNNING' || status === 'PENDING';
      // 终态任务展示耗时（FR-BIZ-21：任务列表含创建时间与耗时）
      var duration = durationText(task);
      var checked = !!state.selectedTaskIds[task.taskId];
      var name = task.taskName || task.fileName || ('任务 ' + task.taskId);

      return ''
        + '<div class="task' + (isActive ? ' is-active' : '') + '" data-task-id="' + task.taskId + '">'
        + '  <label class="task__check" title="选择该任务">'
        + '    <input type="checkbox" data-task-check="' + task.taskId + '"'
        +      (checked ? ' checked' : '') + ' aria-label="选择任务 ' + escapeHtml(name) + '">'
        + '  </label>'
        + '  <button class="task__open" type="button" data-task-id="' + task.taskId + '">'
        + '    <span class="task__top">'
        + '      <span class="task__name">' + escapeHtml(name) + '</span>'
        + '      <span class="status status--' + escapeHtml(status) + '">' + escapeHtml(STATUS_LABEL[status] || status) + '</span>'
        + '    </span>'
        + '    <span class="task__bottom">'
        + '      <span>' + escapeHtml(formatTime(task.createTime)) + '</span>'
        + '      <span class="task__count">' + formatNumber(total) + ' 条</span>'
        +      (duration ? '    <span class="task__duration">' + escapeHtml(duration) + '</span>' : '')
        + '    </span>'
        +      (status === 'FAILED' && task.errorMessage
          ? '    <span class="task__error" title="' + escapeHtml(task.errorMessage) + '">'
            + escapeHtml(task.errorMessage) + '</span>'
          : '')
        +      (showMeter
          ? '    <span class="meter task__meter"><i style="width:' + percent + '%"></i></span>'
          : '')
        + '  </button>'
        +      (status === 'FAILED'
          ? '  <button class="task__retry" type="button" data-task-retry="' + task.taskId + '"'
            + ' title="重新分析该任务">重试</button>'
          : '')
        + '</div>';
    }).join('');

    host.innerHTML = html;
    updateTaskBatchBar();
  }

  /**
   * 计算任务耗时文案。
   * @param {object} task 任务
   * @returns {string} 耗时文案，未结束或时间缺失时返回空串
   */
  function durationText(task) {
    if (FINAL_STATUS.indexOf(task.status) < 0) {
      return '';
    }
    var start = toDate(task.startTime) || toDate(task.createTime);
    var end = toDate(task.finishTime);
    if (!start || !end || end < start) {
      return '';
    }
    var minutes = Math.round((end - start) / 60000);
    if (minutes < 1) {
      return '耗时 <1 分钟';
    }
    return minutes >= 60
      ? '耗时 ' + (minutes / 60).toFixed(1) + ' 小时'
      : '耗时 ' + minutes + ' 分钟';
  }

  /* ==========================================================================
     任务批量操作 / 重命名 / 快速重试
     ========================================================================== */

  /**
   * 刷新任务批量操作条的显示状态。
   */
  function updateTaskBatchBar() {
    var count = Object.keys(state.selectedTaskIds).length;
    $('taskBatchCount').textContent = count;
    $('taskBatch').hidden = count === 0;
  }

  /**
   * 切换单个任务的选中状态。
   * @param {number} taskId  任务编号
   * @param {boolean} checked 是否选中
   */
  function toggleTaskSelection(taskId, checked) {
    if (checked) {
      state.selectedTaskIds[taskId] = true;
    } else {
      delete state.selectedTaskIds[taskId];
    }
    updateTaskBatchBar();
  }

  /**
   * 清空任务批量选择。
   */
  function clearTaskSelection() {
    state.selectedTaskIds = {};
    renderTasks();
  }

  /**
   * 批量删除所选任务。
   */
  async function batchDeleteTasks() {
    var ids = Object.keys(state.selectedTaskIds).map(Number);
    if (!ids.length) {
      return;
    }
    if (!window.confirm('确定删除选中的 ' + ids.length + ' 个任务吗？删除后不可恢复。')) {
      return;
    }
    var button = $('taskBatchDeleteBtn');
    button.disabled = true;
    try {
      var result = await api.post('/api/task/batch-delete', { taskIds: ids });
      toast('已删除 ' + result.deleted + ' 个任务'
        + (result.skipped ? '，跳过 ' + result.skipped + ' 个执行中任务' : ''), 'ok');
      state.selectedTaskIds = {};
      var removedCurrent = state.currentTask && ids.indexOf(state.currentTask.taskId) >= 0;
      if (removedCurrent) {
        state.currentTask = null;
        stopPolling();
      }
      await loadTasks();
      if (state.currentTask) {
        await refreshTaskDetail();
      } else {
        refreshTaskDetail();
      }
    } catch (error) {
      reportError(error);
    } finally {
      button.disabled = false;
    }
  }

  /**
   * 快速重试失败任务。
   * @param {number} taskId 任务编号
   */
  async function retryTask(taskId) {
    try {
      await api.post('/api/task/' + taskId + '/run');
      toast('已提交重新分析，请稍候查看进度', 'ok');
      await loadTasks();
      await selectTask(taskId);
    } catch (error) {
      reportError(error);
    }
  }

  /**
   * 打开重命名弹窗。
   */
  function openRename() {
    var task = state.currentTask;
    if (!task) {
      return;
    }
    state.renameTargetId = task.taskId;
    $('renameInput').value = task.taskName || task.fileName || ('任务 ' + task.taskId);
    $('renameError').hidden = true;
    $('renameModal').hidden = false;
    $('renameInput').focus();
    $('renameInput').select();
  }

  /**
   * 关闭重命名弹窗。
   */
  function closeRename() {
    var modal = $('renameModal');
    if (!modal || modal.hidden) {
      return;
    }
    modal.hidden = true;
    state.renameTargetId = null;
  }

  /**
   * 提交任务重命名。
   */
  async function submitRename() {
    var taskId = state.renameTargetId;
    var name = $('renameInput').value.trim();
    if (!taskId) {
      return;
    }
    if (!name) {
      $('renameError').textContent = '任务名称不能为空';
      $('renameError').hidden = false;
      return;
    }
    var button = $('renameSubmitBtn');
    button.disabled = true;
    try {
      var updated = await api.post('/api/task/' + taskId + '/rename', { taskName: name });
      state.tasks.forEach(function (item) {
        if (item.taskId === taskId) {
          item.taskName = updated.taskName;
        }
      });
      if (state.currentTask && state.currentTask.taskId === taskId) {
        state.currentTask.taskName = updated.taskName;
        renderTaskbar(state.currentTask);
      }
      renderTasks();
      closeRename();
      toast('任务名称已更新', 'ok');
      loadDashboard();
    } catch (error) {
      $('renameError').textContent = (error && error.message) || '重命名失败';
      $('renameError').hidden = false;
    } finally {
      button.disabled = false;
    }
  }

  /**
   * 渲染任务列表分页控件。
   */
  function renderTaskPager() {
    var query = state.taskQuery;
    var host = $('taskPager');
    if (!host) {
      return;
    }
    if (query.pages <= 1) {
      host.classList.remove('is-visible');
      host.innerHTML = '';
      return;
    }
    host.classList.add('is-visible');
    host.innerHTML = ''
      + '<span class="task-pager__info">第 ' + query.pageNum + ' / ' + query.pages + ' 页</span>'
      + '<span class="task-pager__btns">'
      + '  <button class="page-btn" type="button" data-task-page="prev"'
      + (query.pageNum <= 1 ? ' disabled' : '') + '>上一页</button>'
      + '  <button class="page-btn" type="button" data-task-page="next"'
      + (query.pageNum >= query.pages ? ' disabled' : '') + '>下一页</button>'
      + '</span>';
  }

  /* ==========================================================================
     任务详情
     ========================================================================== */

  /**
   * 选中并加载任务详情。
   * @param {number} taskId 任务编号
   */
  async function selectTask(taskId) {
    var task = state.tasks.filter(function (item) {
      return item.taskId === taskId;
    })[0];

    // 从看板/设置页点击任务时，先切回工作台
    setView('workspace', false);

    state.currentTask = task || { taskId: taskId };
    // 使切换前尚未返回的结果/关键词请求失效，避免旧响应覆盖新任务数据
    state.resultSeq++;
    state.keywordSeq++;
    state.trendSeq++;
    state.statSeq++;
    state.detailSeq++;
    // 切换任务时重置结果查询条件
    state.resultQuery.pageNum = 1;
    state.resultQuery.sentiment = '';
    state.resultQuery.keyword = '';
    state.resultQuery.needReview = '';
    state.resultQuery.reviewed = '';
    state.resultQuery.sortBy = '';
    state.resultQuery.sortOrder = '';
    state.selectedResultIds = {};
    state.cloudSentiment = 'ALL';
    $('sentimentFilter').value = '';
    $('reviewFilter').value = '';
    $('resultSearch').value = '';
    $('confidenceMin').value = '';
    $('confidenceMax').value = '';
    updateSortArrow();
    $('cloudSeg').querySelectorAll('.seg__btn').forEach(function (btn) {
      btn.classList.toggle('is-active', btn.dataset.sentiment === 'ALL');
    });

    renderTasks();
    await refreshTaskDetail();
  }

  /**
   * 重新拉取当前任务的详情与各项结果。
   */
  async function refreshTaskDetail() {
    var task = state.currentTask;
    if (!task) {
      applyViewVisibility();
      return;
    }

    var taskId = task.taskId;
    var seq = ++state.detailSeq;

    // 任务详情以接口为准，列表中的字段可能滞后于进度
    try {
      var detail = await api.get('/api/task/' + taskId);
      // 快速切换任务或重复刷新时，丢弃过期响应，避免旧任务覆盖当前任务
      if (seq !== state.detailSeq || !state.currentTask || state.currentTask.taskId !== taskId) {
        return;
      }
      state.currentTask = detail;
    } catch (error) {
      if (seq === state.detailSeq) {
        reportError(error);
      }
      return;
    }
    task = state.currentTask;

    applyViewVisibility();
    renderTaskbar(task);
    renderEmptyResults();

    // 容器可见后图表才能拿到正确尺寸
    requestAnimationFrame(function () {
      charts.resize();
    });

    var isRunning = FINAL_STATUS.indexOf(task.status) < 0;
    if (isRunning) {
      // 分析中：先展示进度，结果数据等结束后再取
      $('runBar').hidden = false;
      updateRunBar(task.status, task.processedCount, task.totalCount);
      startPolling();
      return;
    }

    $('runBar').hidden = true;
    stopPolling();
    await loadTaskResults(task.taskId);
  }

  /**
   * 渲染任务信息条。
   * @param {object} task 任务
   */
  function renderTaskbar(task) {
    var status = task.status || 'PENDING';
    $('taskName').textContent = task.taskName || task.fileName || ('任务 ' + task.taskId);

    var meta = [
      task.fileName || '未知文件',
      formatSize(task.fileSize),
      '共 ' + formatNumber(task.totalCount) + ' 条评论',
      '模型 ' + (task.modelVersion || '—'),
      '创建于 ' + formatTime(task.createTime, true)
    ];
    $('taskMeta').textContent = meta.join('  /  ');

    var pill = $('taskStatusPill');
    pill.className = 'pill pill--' + status;
    pill.textContent = STATUS_LABEL[status] || status;

    var isRunning = FINAL_STATUS.indexOf(status) < 0;
    var canRun = status === 'PENDING' || status === 'FAILED';
    // 后端仅允许待执行/失败任务重新分析，前端同步按钮状态，避免必然失败的请求
    $('runBtn').disabled = !canRun;
    $('runBtn').title = canRun ? '' : '仅待执行或失败的任务可重新分析';
    $('cancelBtn').hidden = status !== 'RUNNING';
    $('deleteBtn').disabled = isRunning;
    $('exportBtn').disabled = isRunning;
    // 未完成任务没有结果数据，报告与分析导出都不可用
    $('reportBtn').disabled = isRunning;

    // 失败任务直接展示落库的失败原因，避免用户只能看到状态不知道问题在哪
    var errorBox = $('taskError');
    if (status === 'FAILED' && task.errorMessage) {
      errorBox.textContent = '失败原因：' + task.errorMessage;
      errorBox.hidden = false;
    } else {
      errorBox.textContent = '';
      errorBox.hidden = true;
    }
  }

  /**
   * 更新整体进度条。
   * @param {string} status    任务状态
   * @param {number} processed 已处理条数
   * @param {number} total     总条数
   */
  function updateRunBar(status, processed, total) {
    var done = Number(processed || 0);
    var all = Number(total || 0);
    var percent = all ? Math.min(100, Math.round((done / all) * 100)) : 0;
    $('runLabel').textContent = status === 'PENDING' ? '任务排队中，等待开始分析' : '正在分析评论情感';
    $('runValue').textContent = formatNumber(done) + ' / ' + formatNumber(all) + ' 条（' + percent + '%）';
    $('runBarFill').style.width = percent + '%';
  }

  /**
   * 清空结果区域，用于任务未完成时的占位。
   */
  function renderEmptyResults() {
    $('summaryTotal').textContent = '正在读取结果…';
    setStatPlaceholder('pos');
    setStatPlaceholder('neg');
    setStatPlaceholder('neu');
    $('metrics').querySelector('[data-role="avgConfidence"]').textContent = '—';
    $('metrics').querySelector('[data-role="reviewCount"]').textContent = '—';
    $('metrics').querySelector('[data-role="errorCount"]').textContent = '—';
    $('rankList').innerHTML = '<li class="rank__item"><span class="rank__no">—</span><span class="rank__word">暂无数据</span><span class="rank__weight"></span></li>';
    $('taskTrendCard').hidden = true;
    $('confidenceAside').textContent = '按 0.1 区间统计';
    $('qualityAside').textContent = '基于已复核样本';
    $('qualityBody').innerHTML = '<p class="quality__empty">选择任务后展示复核质量</p>';
    charts.renderConfidence($('confidenceChart'), null);
    charts.renderNegativeTop($('negativeChart'), []);
    renderResultRows([]);
    renderPager();
  }

  /**
   * 设置单个情感读数。
   * 三色占比条位于概览卡的 #stats 之外，因此在任务详情范围内统一查找。
   * @param {string} key    pos / neg / neu
   * @param {number} count  条数
   * @param {number} ratio  占比（0~1）
   */
  function setStat(key, count, ratio) {
    var scope = $('taskContent');
    var countEl = scope.querySelector('[data-role="' + key + 'Count"]');
    var text = formatNumber(count);
    countEl.textContent = text;
    scope.querySelector('[data-role="' + key + 'Ratio"]').textContent = (ratio * 100).toFixed(1) + '%';
    scope.querySelector('[data-role="' + key + 'Bar"]').style.width = (ratio * 100).toFixed(2) + '%';
    // 兜底：任何外部脚本若再次改写读数，500ms 后按接口值纠正，保证与占比一致
    if (countEl.__statGuard) {
      clearTimeout(countEl.__statGuard);
    }
    countEl.__statGuard = setTimeout(function () {
      if (countEl.textContent !== text) {
        countEl.textContent = text;
      }
    }, 500);
  }

  /**
   * 任务切换过渡态：数字位显示占位符，避免先亮出 0。
   * @param {string} key pos / neg / neu
   */
  function setStatPlaceholder(key) {
    var scope = $('taskContent');
    var countEl = scope.querySelector('[data-role="' + key + 'Count"]');
    if (countEl.__statGuard) {
      clearTimeout(countEl.__statGuard);
      countEl.__statGuard = null;
    }
    countEl.textContent = '—';
    scope.querySelector('[data-role="' + key + 'Ratio"]').textContent = '—';
    scope.querySelector('[data-role="' + key + 'Bar"]').style.width = '0%';
  }

  /**
   * 加载当前任务的全部结果视图（统计、词云、明细）。
   * @param {number} taskId 任务编号
   */
  async function loadTaskResults(taskId) {
    await Promise.all([
      loadStatistics(taskId),
      loadKeywords(taskId),
      loadConfidence(taskId),
      loadNegativeTop(taskId),
      loadReviewQuality(taskId),
      loadTrend(taskId),
      loadResults(taskId)
    ]);
  }

  /**
   * 加载置信度分布直方图。
   * @param {number} taskId 任务编号
   */
  async function loadConfidence(taskId) {
    try {
      var data = await api.get('/api/result/confidence/' + taskId);
      if (state.currentTask && state.currentTask.taskId !== taskId) {
        return;
      }
      charts.renderConfidence($('confidenceChart'), data);
      var below = Number((data && data.belowThresholdCount) || 0);
      var ratio = Number((data && data.belowThresholdRatio) || 0) * 100;
      $('confidenceAside').textContent = below
        ? '低于阈值 ' + formatNumber(below) + ' 条（' + ratio.toFixed(1) + '%）'
        : '全部高于复核阈值';
    } catch (error) {
      reportError(error);
    }
  }

  /**
   * 加载负面评论关键词 Top 10。
   * @param {number} taskId 任务编号
   */
  async function loadNegativeTop(taskId) {
    try {
      var list = await api.get('/api/result/keywords/' + taskId, {
        sentiment: 'NEGATIVE',
        topN: 10
      });
      if (state.currentTask && state.currentTask.taskId !== taskId) {
        return;
      }
      charts.renderNegativeTop($('negativeChart'), list);
    } catch (error) {
      reportError(error);
    }
  }

  /**
   * 加载并渲染复核质量面板（一致率、改判方向、混淆矩阵）。
   * @param {number} taskId 任务编号
   */
  async function loadReviewQuality(taskId) {
    try {
      var data = await api.get('/api/result/review-quality/' + taskId);
      if (state.currentTask && state.currentTask.taskId !== taskId) {
        return;
      }
      renderReviewQuality(data);
    } catch (error) {
      reportError(error);
    }
  }

  /**
   * 渲染复核质量面板。
   * @param {object} data ReviewQualityVO
   */
  function renderReviewQuality(data) {
    var body = $('qualityBody');
    var reviewed = Number((data && data.reviewedCount) || 0);
    if (!reviewed) {
      $('qualityAside').textContent = '基于已复核样本';
      body.innerHTML = '<p class="quality__empty">该任务还没有人工复核记录，完成复核后可在此查看模型与人工的一致率、改判方向与混淆矩阵。</p>';
      return;
    }

    var agreement = Number(data.agreementCount || 0);
    var corrected = Number(data.correctedCount || 0);
    var rate = data.agreementRate === null || data.agreementRate === undefined
      ? 0
      : Number(data.agreementRate);
    $('qualityAside').textContent = '已复核 ' + formatNumber(reviewed) + ' 条';

    var labels = data.labels || [];
    var names = data.labelNames || [];
    var matrix = data.matrix || [];

    // 矩阵单元格查找表
    var cellMap = {};
    matrix.forEach(function (cell) {
      cellMap[cell.modelLabel + '|' + cell.humanLabel] = Number(cell.count || 0);
    });

    var matrixHtml = '<table class="matrix-table"><thead><tr><th>模型 \\ 人工</th>';
    names.forEach(function (name) {
      matrixHtml += '<th>' + escapeHtml(name) + '</th>';
    });
    matrixHtml += '</tr></thead><tbody>';
    labels.forEach(function (modelLabel, rowIndex) {
      matrixHtml += '<tr><th>' + escapeHtml(names[rowIndex] || modelLabel) + '</th>';
      labels.forEach(function (humanLabel) {
        var count = cellMap[modelLabel + '|' + humanLabel] || 0;
        var cls = modelLabel === humanLabel ? ' class="diag"' : (count ? '' : ' class="zero"');
        matrixHtml += '<td' + cls + '>' + count + '</td>';
      });
      matrixHtml += '</tr>';
    });
    matrixHtml += '</tbody></table>';

    var corrections = data.corrections || [];
    var maxCount = corrections.reduce(function (max, item) {
      return Math.max(max, Number(item.count || 0));
    }, 1);
    var correctionsHtml = corrections.length
      ? '<ul class="correction-list">' + corrections.map(function (item) {
        var width = (Number(item.count || 0) / maxCount) * 100;
        return '<li>'
          + '<span>' + escapeHtml(sentimentName(item.fromLabel))
          + ' → ' + escapeHtml(sentimentName(item.toLabel)) + '</span>'
          + '<span class="bar"><i style="width:' + width.toFixed(1) + '%"></i></span>'
          + '<b>' + formatNumber(item.count) + '</b>'
          + '</li>';
      }).join('') + '</ul>'
      : '<p class="quality__empty" style="padding:12px 0;">没有改判，模型与人工结论完全一致</p>';

    body.innerHTML = ''
      + '<div class="quality__score">'
      + '  <strong>' + (rate * 100).toFixed(1) + '%</strong>'
      + '  <span>模型与人工一致率</span>'
      + '  <dl>'
      + '    <div><dt>已复核</dt><dd>' + formatNumber(reviewed) + '</dd></div>'
      + '    <div><dt>一致</dt><dd>' + formatNumber(agreement) + '</dd></div>'
      + '    <div><dt>改判</dt><dd>' + formatNumber(corrected) + '</dd></div>'
      + '  </dl>'
      + '</div>'
      + '<div class="quality__grid">'
      + '  <div>'
      + '    <p class="quality__block-title">模型 / 人工混淆矩阵（对角线为一致）</p>'
      +      matrixHtml
      + '  </div>'
      + '  <div>'
      + '    <p class="quality__block-title">改判方向分布</p>'
      +      correctionsHtml
      + '  </div>'
      + '</div>';
  }

  /**
   * 情感标签转中文。
   * @param {string} label POSITIVE / NEGATIVE / NEUTRAL
   * @returns {string} 中文名
   */
  function sentimentName(label) {
    return charts.SENTIMENT_LABEL[label] || label || '—';
  }

  /**
   * 加载并渲染情感趋势（FR-BIZ-18）。
   *
   * 源文件没有时间列时后端返回空数据点，此时整张趋势卡隐藏。
   * @param {number} taskId 任务编号
   */
  async function loadTrend(taskId) {
    var seq = ++state.trendSeq;
    var card = $('taskTrendCard');
    try {
      var data = await api.get('/api/result/trend/' + taskId);
      if (seq !== state.trendSeq) {
        return;
      }
      var points = (data && data.points) || [];
      if (!points.length) {
        card.hidden = true;
        return;
      }
      card.hidden = false;
      $('taskTrendAside').textContent = data.granularity === 'hour'
        ? '按小时聚合'
        : '按天聚合';
      // 容器由隐藏转为可见后才能拿到正确尺寸
      requestAnimationFrame(function () {
        charts.renderSentimentTrend($('taskTrendChart'), points, data.granularity);
      });
    } catch (error) {
      if (seq === state.trendSeq) {
        card.hidden = true;
        reportError(error);
      }
    }
  }

  /**
   * 加载情感统计并渲染概览与饼图。
   * @param {number} taskId 任务编号
   */
  async function loadStatistics(taskId) {
    var seq = ++state.statSeq;
    try {
      var stats = await api.get('/api/result/statistics/' + taskId);
      // 快速切换任务时，旧任务的统计响应不能覆盖当前任务
      if (seq !== state.statSeq || !state.currentTask || state.currentTask.taskId !== taskId) {
        return;
      }
      var total = Number((stats && stats.totalCount) || 0);
      var positive = Number(stats.positiveCount || 0);
      var negative = Number(stats.negativeCount || 0);
      var neutral = Number(stats.neutralCount || 0);
      // 占比统一由条数现算，保证概览读数、三色条与饼图三者完全一致
      var ratioOf = function (count) {
        return total ? count / total : 0;
      };

      $('summaryTotal').textContent = '共 ' + formatNumber(total) + ' 条评论';
      setStat('pos', positive, ratioOf(positive));
      setStat('neg', negative, ratioOf(negative));
      setStat('neu', neutral, ratioOf(neutral));

      var avg = stats.avgConfidence;
      $('metrics').querySelector('[data-role="avgConfidence"]').textContent =
        (avg === null || avg === undefined || avg === '') ? '—' : (Number(avg) * 100).toFixed(1) + '%';
      $('metrics').querySelector('[data-role="reviewCount"]').textContent = formatNumber(stats.reviewCount);
      $('metrics').querySelector('[data-role="errorCount"]').textContent = formatNumber(stats.errorCount);

      charts.renderPie($('pieChart'), stats);
    } catch (error) {
      reportError(error);
    }
  }

  /**
   * 加载热点词并渲染词云与排名。
   * @param {number} taskId 任务编号
   */
  async function loadKeywords(taskId) {
    var seq = ++state.keywordSeq;
    try {
      var list = await api.get('/api/result/keywords/' + taskId, {
        sentiment: state.cloudSentiment,
        topN: 50
      });
      // 快速切换任务/情感时，丢弃过期响应
      if (seq !== state.keywordSeq) {
        return;
      }
      // "排名"按权重降序才有意义，因此不依赖返回顺序
      var keywords = (list || []).slice().sort(function (a, b) {
        return Number(b.weight || 0) - Number(a.weight || 0);
      });

      charts.renderCloud($('cloudChart'), keywords, state.cloudSentiment);

      var maxWeight = keywords.reduce(function (max, item) {
        return Math.max(max, Number(item.weight || 0));
      }, 0);
      var top = keywords.slice(0, 12);
      $('rankList').innerHTML = top.length
        ? top.map(function (item, index) {
          var weight = Number(item.weight || 0);
          var ratio = maxWeight ? (weight / maxWeight) * 100 : 0;
          return ''
            + '<li class="rank__item">'
            + '  <span class="rank__no">' + pad(index + 1) + '</span>'
            + '  <span class="rank__word" title="' + escapeHtml(item.word) + '">' + escapeHtml(item.word) + '</span>'
            + '  <span class="rank__weight">' + weight.toFixed(4) + '</span>'
            + '  <span class="rank__bar"><i style="width:' + ratio.toFixed(1) + '%"></i></span>'
            + '</li>';
        }).join('')
        : '<li class="rank__item"><span class="rank__no">—</span><span class="rank__word">暂无数据</span><span class="rank__weight"></span></li>';
    } catch (error) {
      if (seq === state.keywordSeq) {
        reportError(error);
      }
    }
  }

  /**
   * 加载结果明细分页数据。
   *
   * 支持情感标签、置信度区间与关键词组合筛选（FR-BIZ-20）。
   * @param {number} taskId 任务编号
   */
  async function loadResults(taskId) {
    var query = state.resultQuery;
    var seq = ++state.resultSeq;
    try {
      var page = await api.get('/api/result/list', {
        pageNum: query.pageNum,
        pageSize: query.pageSize,
        taskId: taskId,
        sentiment: query.sentiment,
        keyword: query.keyword,
        needReview: query.needReview,
        reviewed: query.reviewed,
        sortBy: query.sortBy,
        sortOrder: query.sortOrder,
        minConfidence: $('confidenceMin').value,
        maxConfidence: $('confidenceMax').value
      });
      // 快速切换任务/筛选时，丢弃过期响应
      if (seq !== state.resultSeq) {
        return;
      }
      var rows = (page && page.list) || [];
      query.total = Number((page && page.total) || 0);
      query.pages = Number((page && page.pages) || 0);
      var currentPage = Number((page && page.pageNum) || query.pageNum);
      // 复核/删除后当前页可能越界（例如待复核筛选下清空最后一页），自动回退到有效页
      if (query.pages > 0 && currentPage > query.pages) {
        query.pageNum = query.pages;
        return loadResults(taskId);
      }
      query.pageNum = query.pages > 0 ? Math.max(1, currentPage) : 1;
      // 翻页或筛选变化后清空勾选，避免对上一页数据误操作
      state.selectedResultIds = {};
      renderResultRows(rows);
      renderPager();
    } catch (error) {
      if (seq === state.resultSeq) {
        reportError(error);
      }
    }
  }

  /**
   * 渲染结果表格主体。
   * 无数据时隐藏表格、改用独立提示块，避免整宽单元格在横向滚动时被裁切。
   * @param {Array} rows 结果列表
   */
  function renderResultRows(rows) {
    var body = $('resultBody');
    var table = $('resultTable');
    var empty = $('resultEmpty');

    // 供人工复核弹窗按 resultId 取回完整行数据
    state.resultRows = rows || [];
    // 先同步批量条与全选框，空结果时也要把批量条收起来
    updateResultBatchBar();

    if (!rows.length) {
      body.innerHTML = '';
      table.hidden = true;
      empty.hidden = false;
      return;
    }

    table.hidden = false;
    empty.hidden = true;
    body.innerHTML = rows.map(function (row) {
      var sentiment = row.sentiment || 'NEUTRAL';
      var confidence = (row.confidence === null || row.confidence === undefined)
        ? '—'
        : (Number(row.confidence) * 100).toFixed(1) + '%';
      var needReview = Number(row.needReview) === 1;
      var reviewed = Number(row.reviewed) === 1;
      // 长评论默认折叠两行，避免把行高撑得过高
      var contentText = row.content == null ? '' : String(row.content);
      var isLong = contentText.length > 90;

      // 复核列：待复核 / 已人工复核 / 置信度达标无需复核，三者语义分开
      var reviewCell = '<span class="flag--off">—</span>';
      if (row.needReview !== null && row.needReview !== undefined) {
        if (needReview) {
          reviewCell = '<button class="review-tag review-tag--on" type="button"'
            + ' data-result-id="' + escapeHtml(row.resultId) + '"'
            + ' title="点击进入人工复核">待复核</button>';
        } else if (reviewed) {
          reviewCell = '<button class="review-tag review-tag--off" type="button"'
            + ' data-result-id="' + escapeHtml(row.resultId) + '"'
            + ' title="点击重新复核或调整结论">已复核</button>';
        } else {
          // 高置信度样本默认无需复核，但仍允许人工主动复核
          reviewCell = '<button class="review-tag review-tag--off" type="button"'
            + ' data-result-id="' + escapeHtml(row.resultId) + '"'
            + ' title="置信度高于阈值，如需仍可人工复核">无需复核</button>';
        }
      }

      return ''
        + '<tr>'
        + '  <td class="col-check">'
        + '    <input type="checkbox" data-result-check="' + escapeHtml(row.resultId) + '"'
        +        (state.selectedResultIds[row.resultId] ? ' checked' : '')
        +        ' aria-label="选择该条结果">'
        + '  </td>'
        + '  <td class="cell-id">' + escapeHtml(row.commentId) + '</td>'
        + '  <td class="cell-content">'
        + '    <span class="cell-content__text' + (isLong ? ' is-clamp' : '') + '">'
        +      escapeHtml(contentText) + '</span>'
        +      (isLong ? '<button class="cell-content__toggle" type="button" data-expand="1">展开</button>' : '')
        + '  </td>'
        + '  <td><span class="tag tag--' + escapeHtml(sentiment) + '">'
        +      escapeHtml(charts.SENTIMENT_LABEL[sentiment] || sentiment) + '</span></td>'
        + '  <td class="cell-confidence">' + confidence + '</td>'
        + '  <td class="cell-keywords">' + renderKeywordChips(row.keywords) + '</td>'
        + '  <td>' + reviewCell + '</td>'
        + '  <td class="cell-time">' + escapeHtml(formatTime(row.createTime, true)) + '</td>'
        + '</tr>';
    }).join('');

  }

  /**
   * 按关键词筛选结果明细（关键词胶囊、词云点击共用）。
   * @param {string} word 关键词
   */
  function applyKeywordFilter(word) {
    if (!state.currentTask || !word) {
      return;
    }
    $('resultSearch').value = word;
    state.resultQuery.keyword = word;
    state.resultQuery.pageNum = 1;
    loadResults(state.currentTask.taskId);
    scrollToResults();
  }

  /**
   * 按情感筛选结果明细（饼图扇区点击用）。
   * @param {string} sentiment POSITIVE / NEGATIVE / NEUTRAL
   */
  function applySentimentFilter(sentiment) {
    if (!state.currentTask || !sentiment) {
      return;
    }
    $('sentimentFilter').value = sentiment;
    state.resultQuery.sentiment = sentiment;
    state.resultQuery.pageNum = 1;
    loadResults(state.currentTask.taskId);
    scrollToResults();
  }

  /**
   * 平滑滚动到结果表格，便于看到联动筛选结果。
   */
  function scrollToResults() {
    var table = $('resultTable');
    if (table && table.scrollIntoView) {
      table.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  /**
   * 渲染关键词胶囊，点击即按该词筛选。
   * @param {string} keywords 逗号分隔的关键词
   * @returns {string} HTML
   */
  function renderKeywordChips(keywords) {
    var words = String(keywords || '').split(',').map(function (word) {
      return word.trim();
    }).filter(Boolean);
    if (!words.length) {
      return '—';
    }
    return words.map(function (word) {
      return '<button class="keyword-chip" type="button" data-keyword="'
        + escapeHtml(word) + '">' + escapeHtml(word) + '</button>';
    }).join('');
  }

  /**
   * 刷新结果批量复核条的显示状态与全选框。
   */
  function updateResultBatchBar() {
    var count = Object.keys(state.selectedResultIds).length;
    $('batchCount').textContent = count;
    $('batchBar').hidden = count === 0;
    var all = $('resultCheckAll');
    var rows = state.resultRows || [];
    var selectedOnPage = rows.filter(function (row) {
      return state.selectedResultIds[row.resultId];
    }).length;
    all.checked = rows.length > 0 && selectedOnPage === rows.length;
    all.indeterminate = selectedOnPage > 0 && selectedOnPage < rows.length;
  }

  /**
   * 清空结果批量选择并重绘表格。
   */
  function clearResultSelection() {
    state.selectedResultIds = {};
    renderResultRows(state.resultRows);
  }

  /**
   * 提交批量复核。
   */
  async function submitBatchReview() {
    var ids = Object.keys(state.selectedResultIds).map(Number);
    if (!ids.length) {
      return;
    }
    var sentiment = $('batchSentiment').value;
    var button = $('batchReviewBtn');
    button.disabled = true;
    button.textContent = '提交中…';
    try {
      var count = await api.post('/api/result/batch-review', {
        resultIds: ids,
        reviewed: true,
        sentiment: sentiment
      });
      toast('已批量复核 ' + count + ' 条：' + (charts.SENTIMENT_LABEL[sentiment] || sentiment), 'ok');
      state.selectedResultIds = {};
      // 复核会改变情感分布、待复核数与复核一致率，统计、明细与质量面板一起刷新
      if (state.currentTask) {
        await Promise.all([
          loadStatistics(state.currentTask.taskId),
          loadResults(state.currentTask.taskId),
          loadReviewQuality(state.currentTask.taskId)
        ]);
      }
    } catch (error) {
      reportError(error);
    } finally {
      button.disabled = false;
      button.textContent = '批量复核';
    }
  }

  /**
   * 打开人工复核弹窗。
   *
   * 弹窗集中展示评论原文（关键词高亮）、模型置信度仪表、模型判定与人工结论选项；
   * 只有点击「确认复核」后才会提交复核状态，避免原来的单击即标记。
   * @param {number} resultId 结果编号
   */
  function openReview(resultId) {
    var row = state.resultRows.filter(function (item) {
      return Number(item.resultId) === resultId;
    })[0];
    if (!row) {
      return;
    }
    state.reviewTarget = row;
    state.reviewSelection = row.sentiment || 'NEUTRAL';

    var sentiment = row.sentiment || 'NEUTRAL';
    var confidence = row.confidence === null || row.confidence === undefined
      ? 0
      : Number(row.confidence);

    $('reviewMeta').textContent = '评论号 ' + row.commentId
      + '  ·  分析时间 ' + formatTime(row.createTime, true);

    $('reviewText').innerHTML = highlightKeywords(row.content, row.keywords);
    renderReviewKeywords(row.keywords);

    $('reviewConfidence').textContent = (confidence * 100).toFixed(1) + '%';
    renderReviewGauge(confidence, sentiment);

    var modelTag = $('reviewModelTag');
    modelTag.className = 'tag tag--' + sentiment;
    modelTag.textContent = charts.SENTIMENT_LABEL[sentiment] || sentiment;
    var reviewed = Number(row.reviewed) === 1;
    // 只有真正人工复核过才展示「当前结论」；高置信度未复核仍是模型判定
    $('reviewModelLabel').textContent = reviewed ? '当前结论' : '模型判定';

    selectReviewSentiment(state.reviewSelection);

    // 只有已人工复核的记录允许撤销；待复核/无需复核记录不显示撤销
    $('reviewUndoBtn').hidden = !reviewed;
    // 上一次撤销复核后按钮会被禁用，打开新记录时需要恢复
    $('reviewUndoBtn').disabled = false;
    $('reviewSubmitBtn').disabled = false;
    $('reviewModal').hidden = false;
    $('reviewSubmitBtn').focus();

    updateReviewThresholdTip(confidence);
  }

  /**
   * 绘制置信度环形仪表，颜色跟随模型判定。
   * @param {number} confidence 置信度（0~1）
   * @param {string} sentiment  情感标签
   */
  function renderReviewGauge(confidence, sentiment) {
    var circle = $('reviewGaugeValue');
    var radius = 52;
    var circumference = 2 * Math.PI * radius;
    var ratio = Math.max(0, Math.min(1, confidence));
    circle.style.strokeDasharray = circumference.toFixed(2);
    circle.style.strokeDashoffset = (circumference * (1 - ratio)).toFixed(2);
    circle.style.stroke = SENTIMENT_COLOR[sentiment] || '#A64A2B';
  }

  /**
   * 渲染关键词标签。
   * @param {string} keywords 逗号分隔的关键词
   */
  function renderReviewKeywords(keywords) {
    var words = String(keywords || '').split(',').map(function (word) {
      return word.trim();
    }).filter(Boolean);

    $('reviewKeywords').innerHTML = words.length
      ? words.map(function (word) {
        return '<span class="review__keyword">' + escapeHtml(word) + '</span>';
      }).join('')
      : '<span class="review__keyword">该条未提取到关键词</span>';
  }

  /**
   * 在评论原文中高亮命中的关键词，便于对照复核。
   * @param {string} text     评论原文
   * @param {string} keywords 逗号分隔的关键词
   * @returns {string} 已转义的 HTML
   */
  function highlightKeywords(text, keywords) {
    var escaped = escapeHtml(text || '');
    var words = String(keywords || '').split(',').map(function (word) {
      return escapeHtml(word.trim());
    }).filter(Boolean).sort(function (a, b) {
      return b.length - a.length;
    });
    if (!words.length) {
      return escaped;
    }
    var pattern = words.map(function (word) {
      return word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }).join('|');
    return escaped.replace(new RegExp('(' + pattern + ')', 'gi'), '<mark>$1</mark>');
  }

  /**
   * 读取并缓存低置信度复核阈值，用于解释当前置信度所处区间。
   * @param {number} confidence 置信度（0~1）
   */
  async function updateReviewThresholdTip(confidence) {
    var tip = $('reviewThresholdTip');
    if (state.reviewThreshold === null) {
      try {
        var settings = await api.get('/api/settings');
        state.reviewThreshold = settings && settings.inference
          ? Number(settings.inference.reviewThreshold)
          : 0.6;
      } catch (error) {
        state.reviewThreshold = 0.6;
      }
    }
    // 弹窗已被关闭或切换到别的记录时，不再覆盖提示
    if (!state.reviewTarget || $('reviewModal').hidden) {
      return;
    }
    var threshold = Number(state.reviewThreshold);
    if (confidence < threshold) {
      tip.textContent = '低于复核阈值 ' + (threshold * 100).toFixed(0)
        + '%，属于低置信度样本，请对照原文确认。';
    } else {
      tip.textContent = '高于复核阈值 ' + (threshold * 100).toFixed(0)
        + '%，如仍判断有误可在此调整结论。';
    }
  }

  /**
   * 切换人工复核结论的选中状态。
   * @param {string} sentiment 情感标签
   */
  function selectReviewSentiment(sentiment) {
    state.reviewSelection = sentiment;
    $('reviewOptions').querySelectorAll('.review-option').forEach(function (button) {
      button.classList.toggle('is-active', button.dataset.sentiment === sentiment);
    });
  }

  /**
   * 关闭人工复核弹窗。
   */
  function closeReview() {
    var modal = $('reviewModal');
    if (!modal || modal.hidden) {
      return;
    }
    modal.hidden = true;
    state.reviewTarget = null;
    state.reviewSelection = '';
  }

  /**
   * 提交人工复核结论，或撤销复核标记。
   * @param {boolean} undo true 表示撤销复核
   */
  async function submitReview(undo) {
    var row = state.reviewTarget;
    if (!row) {
      return;
    }
    var button = undo ? $('reviewUndoBtn') : $('reviewSubmitBtn');
    button.disabled = true;
    try {
      if (undo) {
        await api.post('/api/result/' + row.resultId + '/review', { reviewed: false });
        toast('已撤销复核，记录回到待复核队列', 'ok');
      } else {
        var sentiment = state.reviewSelection || row.sentiment;
        await api.post('/api/result/' + row.resultId + '/review', {
          reviewed: true,
          sentiment: sentiment
        });
        toast('复核已提交：' + (charts.SENTIMENT_LABEL[sentiment] || sentiment), 'ok');
      }
      closeReview();
      // 人工结论会改变情感分布、待复核数与复核一致率，三处一起刷新
      if (state.currentTask) {
        await Promise.all([
          loadStatistics(state.currentTask.taskId),
          loadResults(state.currentTask.taskId),
          loadReviewQuality(state.currentTask.taskId)
        ]);
      }
    } catch (error) {
      button.disabled = false;
      reportError(error);
    }
  }

  /**
   * 更新置信度排序箭头与提示。
   */
  function updateSortArrow() {
    var arrow = $('confidenceSortArrow');
    var query = state.resultQuery;
    if (query.sortBy !== 'confidence') {
      arrow.textContent = '↕';
      return;
    }
    arrow.textContent = query.sortOrder === 'desc' ? '↓' : '↑';
  }

  /**
   * 计算分页按钮序列，超过一屏时用省略号收敛。
   * @param {number} current 当前页
   * @param {number} pages   总页数
   * @returns {Array<number|string>} 页码序列，'...' 表示省略
   */
  function pageSequence(current, pages) {
    if (pages <= 7) {
      var all = [];
      for (var i = 1; i <= pages; i++) {
        all.push(i);
      }
      return all;
    }
    if (current <= 4) {
      return [1, 2, 3, 4, 5, '...', pages];
    }
    if (current >= pages - 3) {
      return [1, '...', pages - 4, pages - 3, pages - 2, pages - 1, pages];
    }
    return [1, '...', current - 1, current, current + 1, '...', pages];
  }

  /**
   * 渲染分页控件。
   */
  function renderPager() {
    var query = state.resultQuery;
    var host = $('pager');

    if (!query.total) {
      host.innerHTML = '<span class="pager__info">共 <b>0</b> 条结果</span>';
      return;
    }

    var buttons = pageSequence(query.pageNum, Math.max(query.pages, 1)).map(function (page) {
      if (page === '...') {
        return '<span class="page-gap">…</span>';
      }
      return '<button class="page-btn' + (page === query.pageNum ? ' is-active' : '')
        + '" type="button" data-page="' + page + '">' + page + '</button>';
    }).join('');

    host.innerHTML = ''
      + '<span class="pager__info">共 <b>' + formatNumber(query.total) + '</b> 条结果，第 <b>'
      + query.pageNum + '</b> / <b>' + Math.max(query.pages, 1) + '</b> 页</span>'
      + '<span class="pager__pages">'
      + '  <button class="page-btn" type="button" data-page="prev"' + (query.pageNum <= 1 ? ' disabled' : '') + '>上一页</button>'
      + buttons
      + '  <button class="page-btn" type="button" data-page="next"' + (query.pageNum >= query.pages ? ' disabled' : '') + '>下一页</button>'
      + '</span>';
  }

  /**
   * 翻页。
   * @param {string} target 页码或 prev/next
   */
  function goPage(target) {
    var query = state.resultQuery;
    if (!state.currentTask || !query.pages) {
      return;
    }
    var next = query.pageNum;
    if (target === 'prev') {
      next = Math.max(1, query.pageNum - 1);
    } else if (target === 'next') {
      next = Math.min(query.pages, query.pageNum + 1);
    } else {
      next = Number(target);
    }
    if (next === query.pageNum) {
      return;
    }
    query.pageNum = next;
    loadResults(state.currentTask.taskId);
  }

  /* ==========================================================================
     进度轮询
     ========================================================================== */

  /**
   * 启动进度轮询。
   */
  function startPolling() {
    if (state.pollTimer) {
      return;
    }
    state.pollTimer = setInterval(pollOnce, POLL_INTERVAL);
  }

  /**
   * 停止进度轮询。
   */
  function stopPolling() {
    if (state.pollTimer) {
      clearInterval(state.pollTimer);
      state.pollTimer = null;
    }
  }

  /**
   * 单次轮询：刷新当前任务进度，并低频同步任务列表。
   */
  async function pollOnce() {
    var task = state.currentTask;
    if (!task || state.polling) {
      return;
    }
    // setInterval 不等待上一次请求，慢网络下会叠加并发；用标记跳过本轮
    state.polling = true;
    state.pollTick++;

    try {
      var progress = await api.get('/api/task/' + task.taskId + '/progress');
      // 轮询期间用户可能已切换任务，过期响应直接丢弃
      if (!state.currentTask || state.currentTask.taskId !== task.taskId) {
        return;
      }
      updateRunBar(progress.status, progress.processedCount, progress.totalCount);

      var finished = FINAL_STATUS.indexOf(progress.status) >= 0;
      if (finished) {
        stopPolling();
        $('runBar').hidden = true;
        toast(progress.status === 'SUCCESS' ? '分析完成，结果已更新' : '任务已结束：'
          + (STATUS_LABEL[progress.status] || progress.status),
          progress.status === 'SUCCESS' ? 'ok' : 'info');
        await loadTasks();
        await refreshTaskDetail();
        return;
      }
    } catch (error) {
      reportError(error);
      stopPolling();
      return;
    } finally {
      state.polling = false;
    }

    // 每 4 次轮询（约 6 秒）同步一次任务列表，保持侧栏状态新鲜
    if (hasRunningTask() && state.pollTick % 4 === 0) {
      await loadTasks();
    }
  }

  /* ==========================================================================
     文件上传
     ========================================================================== */

  /**
   * 校验并上传文件。
   * @param {File} file 待上传文件
   */
  async function handleFile(file) {
    if (!file) {
      return;
    }
    // 上传/解析期间再次选择或拖入文件会重复创建任务，这里串行化
    if (state.uploadBusy) {
      toast('上一个文件还在上传解析，请稍候', 'info');
      return;
    }

    var name = file.name || '';
    var ext = name.slice(name.lastIndexOf('.')).toLowerCase();
    if (['.xlsx', '.xls', '.csv', '.txt', '.tsv', '.json'].indexOf(ext) < 0) {
      toast('仅支持 .xlsx / .xls / .csv / .txt / .tsv / .json 格式文件', 'err');
      return;
    }
    if (file.size > MAX_FILE_SIZE) {
      toast('文件大小超过 50 MB 限制，请拆分后上传', 'err');
      return;
    }
    state.uploadBusy = true;

    var meter = $('uploadMeter');
    var bar = $('uploadBar');
    var percentText = $('uploadPercent');
    var stage = $('uploadStage');

    meter.hidden = false;
    bar.style.width = '0%';
    percentText.textContent = '0%';
    stage.textContent = '正在上传并校验文件';

    try {
      var report = await api.upload('/api/file/upload', file, function (percent) {
        bar.style.width = percent + '%';
        percentText.textContent = percent + '%';
        if (percent >= 100) {
          stage.textContent = '文件已上传，正在解析';
        }
      });

      stage.textContent = '解析完成，正在分析';
      percentText.textContent = '100%';

      // 评论列自动识别失败：引导用户从候选列中指定（FR-BIZ-06）
      if (report.needsColumnSelection) {
        stage.textContent = '需要指定评论列';
        openColumnPicker(report);
        return;
      }

      // 新任务置顶后立即选中：回到任务列表第一页再刷新
      state.taskQuery.pageNum = 1;
      await loadTasks();
      await selectTask(report.taskId);
      // 展示解析质量报告（FR-BIZ-10），关闭后即可查看分析结果
      showParseReport(report, file.name);
    } catch (error) {
      reportError(error);
    } finally {
      state.uploadBusy = false;
      setTimeout(function () {
        meter.hidden = true;
      }, 800);
    }
  }

  /* ==========================================================================
     评论列人工指定（FR-BIZ-06）
     ========================================================================== */

  /**
   * 打开评论列选择弹窗。
   * @param {object} report 上传返回的解析报告（含令牌与候选列）
   */
  function openColumnPicker(report) {
    var candidates = report.candidateColumns || [];
    state.pendingColumnReport = report;
    // 默认选中样例文本最长的列：评论正文通常最长的可能性最大
    var defaultIndex = -1;
    var maxLength = -1;
    candidates.forEach(function (item) {
      var length = Number(item.sampleLength || 0);
      if (length > maxLength) {
        maxLength = length;
        defaultIndex = Number(item.index);
      }
    });
    state.columnSelection = defaultIndex;

    $('columnMeta').textContent = (report.fileName || '—')
      + ' · 共 ' + candidates.length + ' 个候选列';
    $('columnError').hidden = true;
    $('columnOptions').innerHTML = candidates.map(function (item) {
      var index = Number(item.index);
      var header = item.header ? escapeHtml(item.header) : '第 ' + (index + 1) + ' 列';
      var sample = item.sample ? escapeHtml(item.sample) : '（该列无内容）';
      return ''
        + '<label class="column-option' + (index === defaultIndex ? ' is-active' : '') + '">'
        + '  <input type="radio" name="commentColumn" value="' + index + '"'
        +      (index === defaultIndex ? ' checked' : '') + '>'
        + '  <span class="column-option__name" title="' + header + '">' + header + '</span>'
        + '  <span class="column-option__sample">'
        + '    <em>' + Number(item.sampleLength || 0) + ' 字</em>' + sample
        + '  </span>'
        + '</label>';
    }).join('');
    $('columnSubmitBtn').disabled = false;
    $('columnModal').hidden = false;
  }

  /**
   * 关闭评论列选择弹窗。
   */
  function closeColumnPicker() {
    var modal = $('columnModal');
    if (!modal || modal.hidden) {
      return;
    }
    modal.hidden = true;
    state.pendingColumnReport = null;
    state.columnSelection = -1;
  }

  /**
   * 提交人工指定的评论列并开始分析。
   */
  async function submitColumn() {
    var report = state.pendingColumnReport;
    if (!report || state.columnSelection < 0) {
      $('columnError').textContent = '请选择一列后再继续';
      $('columnError').hidden = false;
      return;
    }
    var button = $('columnSubmitBtn');
    button.disabled = true;
    button.textContent = '正在导入…';
    try {
      var result = await api.post('/api/file/reimport', {
        token: report.pendingToken,
        column: state.columnSelection
      });
      closeColumnPicker();
      state.taskQuery.pageNum = 1;
      await loadTasks();
      await selectTask(result.taskId);
      showParseReport(result, result.fileName);
    } catch (error) {
      $('columnError').textContent = error && error.message
        ? error.message
        : '导入失败，请重新选择列';
      $('columnError').hidden = false;
    } finally {
      button.disabled = false;
      button.textContent = '确认并开始分析';
    }
  }

  /* ==========================================================================
     智能输入（纯文本 / 网页链接自动识别）
     ========================================================================== */

  /** 输入内容字符上限，与后端 app.input.max-input-chars 一致 */
  var MAX_INPUT_CHARS = 500000;

  /**
   * 识别输入类型，仅用于界面提示；后端会再次校验并执行对应流程。
   * 整段输入只有一个链接时视为网页，其余情况均按纯文本处理。
   * @param {string} value 输入内容
   * @returns {{kind:string, label:string}} 识别结果
   */
  function detectInputKind(value) {
    var text = (value || '').replace(/\u3000/g, ' ').trim();
    if (!text) {
      return { kind: 'EMPTY', label: '自动识别' };
    }
    var isUrl = !/\s/.test(text) && /^(https?:\/\/|www\.)\S+$/i.test(text);
    return isUrl
      ? { kind: 'WEB_PAGE', label: '网页链接' }
      : { kind: 'PLAIN_TEXT', label: '纯文本' };
  }

  /**
   * 根据当前输入刷新识别标签与提示文案。
   */
  function updateSmartHint() {
    var value = $('smartInput').value;
    var text = value.trim();
    var detected = detectInputKind(text);
    var type = $('smartType');
    type.textContent = detected.label;
    type.classList.toggle('is-url', detected.kind === 'WEB_PAGE');
    if (detected.kind === 'EMPTY') {
      $('smartHint').textContent = '支持纯文本 / 网页链接，Ctrl + Enter 提交';
    } else if (detected.kind === 'WEB_PAGE') {
      $('smartHint').textContent = '已识别为网页链接，抓取后可先预览确认正文';
    } else {
      $('smartHint').textContent = '已识别为纯文本 · 共 ' + formatNumber(text.length) + ' 字';
    }
  }

  /**
   * 渲染内容接收回执，明确告知用户已进入分析流程。
   * @param {object} report 后端接收回执
   */
  function showInputReceipt(report) {
    var isWeb = report.sourceType === 'WEB_PAGE';
    $('inputReceipt').hidden = false;
    $('receiptBadge').textContent = isWeb ? '网页已接收' : '文本已接收';
    $('receiptTitle').textContent = isWeb
      ? (report.sourceTitle || report.sourceUrl || '网页正文')
      : '纯文本内容';
    $('receiptDesc').textContent = '正文 ' + formatNumber(report.inputChars) + ' 字，切分为 '
      + formatNumber(report.commentCount) + ' 条评论；任务 #' + report.taskId + ' 已进入分析流程';
    $('receiptMeta').textContent = '接收耗时 '
      + (Number(report.elapsedMs || 0) / 1000).toFixed(2) + ' 秒';
  }

  /**
   * 提交智能输入：后端自动识别文本 / 链接并创建分析任务。
   */
  async function submitSmartInput() {
    var input = $('smartInput');
    var value = input.value.trim();
    if (!value) {
      toast('请先粘贴评论文本或网页链接', 'err');
      input.focus();
      return;
    }
    if (value.length > MAX_INPUT_CHARS) {
      toast('输入内容超过 50 万字，请分段提交', 'err');
      return;
    }
    if (state.smartBusy) {
      return;
    }

    var detected = detectInputKind(value);
    var button = $('smartSubmit');
    state.smartBusy = true;
    button.disabled = true;
    button.textContent = '识别中…';

    // 先给出「正在接收」反馈，避免用户等待期间重复操作
    $('inputReceipt').hidden = false;
    $('receiptBadge').textContent = '正在接收';
    $('receiptTitle').textContent = detected.kind === 'WEB_PAGE'
      ? '正在抓取网页正文…'
      : '正在接收文本内容…';
    $('receiptDesc').textContent = '系统会自动识别并进入分析流程，无需额外操作';
    $('receiptMeta').textContent = '';

    try {
      // 网页链接先抓取正文并让用户确认，避免抽错内容却直接分析
      if (detected.kind === 'WEB_PAGE') {
        var preview = await api.post('/api/input/preview', { content: value });
        $('inputReceipt').hidden = true;
        openPagePreview(preview, value);
        return;
      }

      var report = await api.post('/api/input/analyze', { content: value });
      showInputReceipt(report);
      input.value = '';
      updateSmartHint();
      toast(report.message || '内容已接收，正在分析', 'ok');

      // 新任务置顶后立即选中，与文件上传保持一致的后续流程
      state.taskQuery.pageNum = 1;
      await loadTasks();
      await selectTask(report.taskId);
    } catch (error) {
      $('inputReceipt').hidden = true;
      reportError(error);
    } finally {
      state.smartBusy = false;
      button.disabled = false;
      button.textContent = '开始分析';
    }
  }

  /* ==========================================================================
     网页正文确认（抽取预览 + 用户确认）
     ========================================================================== */

  /**
   * 打开网页正文确认弹窗。
   * @param {object} preview 预览数据
   * @param {string} rawUrl  用户输入的原始链接，用于重新抓取
   */
  function openPagePreview(preview, rawUrl) {
    state.pagePreview = preview;
    state.previewUrl = rawUrl;

    $('previewUrl').textContent = preview.title || preview.url || '—';
    $('previewStats').innerHTML = ''
      + '<div><dt>正文字符</dt><dd>' + formatNumber(preview.inputChars || 0) + '</dd></div>'
      + '<div><dt>段落数</dt><dd>' + formatNumber(preview.paragraphCount || 0) + '</dd></div>'
      + '<div><dt>预计评论条数</dt><dd>' + formatNumber(preview.commentCount || 0) + '</dd></div>'
      + '<div><dt>链接密度</dt><dd>'
      + ((Number(preview.linkDensity || 0) * 100).toFixed(1) + '%') + '</dd></div>';

    var warning = $('previewWarning');
    if (preview.warning) {
      warning.textContent = preview.warning;
      warning.hidden = false;
    } else {
      warning.textContent = '';
      warning.hidden = true;
    }

    $('previewExcerpt').textContent = preview.excerpt || '（未抽取到正文）';
    $('previewConfirmBtn').disabled = false;
    $('previewRetryBtn').disabled = false;
    $('previewModal').hidden = false;
    $('previewConfirmBtn').focus();
  }

  /**
   * 关闭网页正文确认弹窗。
   */
  function closePagePreview() {
    var modal = $('previewModal');
    if (!modal || modal.hidden) {
      return;
    }
    modal.hidden = true;
    state.pagePreview = null;
    state.previewUrl = '';
  }

  /**
   * 确认正文并创建分析任务。
   */
  async function confirmPagePreview() {
    var preview = state.pagePreview;
    if (!preview || !preview.token) {
      return;
    }
    var button = $('previewConfirmBtn');
    button.disabled = true;
    button.textContent = '正在创建任务…';
    try {
      var report = await api.post('/api/input/confirm', { token: preview.token });
      closePagePreview();
      $('smartInput').value = '';
      updateSmartHint();
      showInputReceipt(report);
      toast(report.message || '正文已确认，正在分析', 'ok');

      state.taskQuery.pageNum = 1;
      await loadTasks();
      await selectTask(report.taskId);
    } catch (error) {
      reportError(error);
    } finally {
      button.disabled = false;
      button.textContent = '确认并分析';
    }
  }

  /**
   * 重新抓取当前链接（适用于站点临时返回不完整页面）。
   */
  async function retryPagePreview() {
    var rawUrl = state.previewUrl;
    if (!rawUrl) {
      return;
    }
    var button = $('previewRetryBtn');
    button.disabled = true;
    button.textContent = '抓取中…';
    try {
      var preview = await api.post('/api/input/preview', { content: rawUrl });
      openPagePreview(preview, rawUrl);
      toast('已重新抓取，请再次确认', 'ok');
    } catch (error) {
      reportError(error);
    } finally {
      button.disabled = false;
      button.textContent = '重新抓取';
    }
  }

  /* ==========================================================================
     任务操作
     ========================================================================== */

  /**
   * 重新触发当前任务的分析。
   */
  async function runCurrentTask() {
    var task = state.currentTask;
    if (!task) {
      return;
    }
    $('runBtn').disabled = true;
    try {
      await api.post('/api/task/' + task.taskId + '/run');
      toast('已提交分析，正在处理', 'ok');
      await loadTasks();
      await refreshTaskDetail();
    } catch (error) {
      reportError(error);
      $('runBtn').disabled = false;
    }
  }

  /**
   * 终止当前任务。
   */
  async function cancelCurrentTask() {
    var task = state.currentTask;
    if (!task) {
      return;
    }
    try {
      await api.post('/api/task/' + task.taskId + '/cancel');
      toast('终止请求已受理，将在当前批次结束后停止', 'info');
    } catch (error) {
      reportError(error);
    }
  }

  /**
   * 删除当前任务（逻辑删除）。
   */
  async function deleteCurrentTask() {
    var task = state.currentTask;
    if (!task) {
      return;
    }
    var name = task.taskName || task.fileName || ('任务 ' + task.taskId);
    if (!window.confirm('确定删除任务「' + name + '」吗？删除后不再出现在任务列表中。')) {
      return;
    }
    try {
      await api.del('/api/task/' + task.taskId);
      toast('任务已删除', 'ok');
      state.currentTask = null;
      stopPolling();
      await loadTasks();
      await refreshTaskDetail();
    } catch (error) {
      reportError(error);
    }
  }

  /**
   * 导出当前任务的分析结果。
   *
   * 导出范围由「导出范围」下拉显式决定（FR-BIZ-27）：
   * 全量导出忽略当前筛选；仅当前筛选则携带情感、关键词与复核状态条件。
   */
  async function exportCurrentTask() {
    var task = state.currentTask;
    if (!task) {
      return;
    }
    var button = $('exportBtn');
    button.disabled = true;
    button.textContent = '导出中…';
    try {
      var sentiment = $('sentimentFilter').value;
      var keyword = $('resultSearch').value.trim();
      var reviewValue = $('reviewFilter').value;
      // 导出范围由用户显式选择：全量 / 仅当前筛选
      var scope = $('exportScope').value || 'all';
      var format = $('exportFormat').value || 'xlsx';
      var params = { scope: scope, format: format };
      if (scope === 'current') {
        params.sentiment = sentiment;
        params.keyword = keyword;
        params.needReview = reviewValue === '1' ? '1' : '';
        params.reviewed = reviewValue === '0' ? '1' : '';
        // 置信度区间也是结果筛选项，导出「当前筛选」时必须一并带上
        params.minConfidence = $('confidenceMin').value;
        params.maxConfidence = $('confidenceMax').value;
      }
      var filename = await api.download('/api/result/export/' + task.taskId,
        params, '分析结果_' + task.taskId + '.' + format);
      toast('已导出「' + filename + '」', 'ok');
    } catch (error) {
      reportError(error);
    } finally {
      button.disabled = false;
      button.textContent = '导出结果';
    }
  }

  /**
   * 下载任务分析报告（单文件 HTML，可直接打印为 PDF）。
   */
  async function exportReport() {
    var task = state.currentTask;
    if (!task) {
      return;
    }
    var button = $('reportBtn');
    button.disabled = true;
    button.textContent = '生成中…';
    try {
      var filename = await api.download('/api/result/report/' + task.taskId,
        {}, '分析报告_' + task.taskId + '.html');
      toast('已导出「' + filename + '」', 'ok');
    } catch (error) {
      reportError(error);
    } finally {
      button.disabled = false;
      button.textContent = '导出报告';
    }
  }

  /* ==========================================================================
     任务对比
     ========================================================================== */

  /**
   * 加载任务对比的两个下拉选项。
   */
  async function loadCompareOptions() {
    var left = $('compareLeft');
    var right = $('compareRight');
    try {
      var page = await api.get('/api/task/list', { pageNum: 1, pageSize: 200 });
      var tasks = (page && page.list) || [];
      if (!tasks.length) {
        left.innerHTML = '<option value="">暂无任务</option>';
        right.innerHTML = '<option value="">暂无任务</option>';
        return;
      }
      var options = tasks.map(function (task) {
        var name = task.taskName || task.fileName || ('任务 ' + task.taskId);
        return '<option value="' + task.taskId + '">' + escapeHtml(name)
          + '（' + formatNumber(task.totalCount || 0) + ' 条）</option>';
      }).join('');
      // 保留用户已选项，避免刷新后选择被重置
      var keepLeft = left.value;
      var keepRight = right.value;
      left.innerHTML = options;
      right.innerHTML = options;
      if (keepLeft) {
        left.value = keepLeft;
      }
      if (keepRight) {
        right.value = keepRight;
      } else if (tasks.length > 1) {
        right.value = String(tasks[1].taskId);
      }
    } catch (error) {
      reportError(error);
    }
  }

  /**
   * 执行任务对比：并排展示两个任务的情感分布、关键指标与热点词。
   */
  async function runCompare() {
    var leftId = Number($('compareLeft').value);
    var rightId = Number($('compareRight').value);
    if (!leftId || !rightId) {
      toast('请先选择两个任务', 'err');
      return;
    }
    if (leftId === rightId) {
      toast('请选择两个不同的任务进行对比', 'err');
      return;
    }
    var button = $('compareRunBtn');
    button.disabled = true;
    button.textContent = '对比中…';
    try {
      var results = await Promise.all([
        loadCompareSide(leftId),
        loadCompareSide(rightId)
      ]);
      renderCompare(results[0], results[1]);
    } catch (error) {
      reportError(error);
    } finally {
      button.disabled = false;
      button.textContent = '开始对比';
    }
  }

  /**
   * 读取单个任务用于对比的数据。
   * @param {number} taskId 任务编号
   * @returns {Promise<object>} 任务、统计、热词、复核质量与置信度分布
   */
  async function loadCompareSide(taskId) {
    var values = await Promise.all([
      api.get('/api/task/' + taskId),
      api.get('/api/result/statistics/' + taskId),
      api.get('/api/result/keywords/' + taskId, { sentiment: 'ALL', topN: 20 }),
      api.get('/api/result/review-quality/' + taskId),
      api.get('/api/result/confidence/' + taskId)
    ]);
    return {
      task: values[0] || {},
      stats: values[1] || {},
      keywords: values[2] || [],
      quality: values[3] || {},
      confidence: values[4] || {}
    };
  }

  /**
   * 渲染任务对比结果：结论摘要、指标表、两组对比图与关键词差异。
   * @param {object} left  A 任务数据
   * @param {object} right B 任务数据
   */
  function renderCompare(left, right) {
    var nameA = compareTaskName(left);
    var nameB = compareTaskName(right);

    $('compareEmpty').hidden = true;
    $('compareBody').hidden = false;

    renderCompareSummary(left, right, nameA, nameB);
    renderCompareTable(left, right, nameA, nameB);
    renderCompareWords(left, right, nameA, nameB);

    // 容器由隐藏转为可见后再初始化图表，避免拿到 0 尺寸
    requestAnimationFrame(function () {
      charts.renderCompareSentiment($('compareSentimentChart'), left.stats, right.stats,
        nameA, nameB);
      charts.renderCompareConfidence($('compareConfidenceChart'),
        left.confidence, right.confidence, nameA, nameB);
    });
  }

  /**
   * 取任务用于展示的名称。
   * @param {object} side 单侧数据
   * @returns {string} 任务名
   */
  function compareTaskName(side) {
    var task = side.task || {};
    return task.taskName || task.fileName || ('任务 ' + task.taskId);
  }

  /**
   * 计算占比（0～1）。
   * @param {object} stats 统计对象
   * @param {string} key   条数字段名
   * @returns {number} 占比
   */
  function compareRatio(stats, key) {
    var total = Number((stats && stats.totalCount) || 0);
    if (!total) {
      return 0;
    }
    return Number((stats && stats[key]) || 0) / total;
  }

  /**
   * 渲染自动生成的对比结论。
   *
   * 只在差异足够明显（≥1 个百分点）时输出结论，避免把噪声当成结论。
   *
   * @param {object} left  A 任务数据
   * @param {object} right B 任务数据
   * @param {string} nameA A 任务名
   * @param {string} nameB B 任务名
   */
  function renderCompareSummary(left, right, nameA, nameB) {
    var items = [];
    // 任务名允许用户重命名，拼入 innerHTML 前必须转义
    var labelA = escapeHtml(nameA);
    var labelB = escapeHtml(nameB);
    var posA = compareRatio(left.stats, 'positiveCount') * 100;
    var posB = compareRatio(right.stats, 'positiveCount') * 100;
    var negA = compareRatio(left.stats, 'negativeCount') * 100;
    var negB = compareRatio(right.stats, 'negativeCount') * 100;
    var neuA = compareRatio(left.stats, 'neutralCount') * 100;
    var neuB = compareRatio(right.stats, 'neutralCount') * 100;

    if (Math.abs(posA - posB) >= 1) {
      var posHigher = posA > posB ? labelA : labelB;
      items.push('正面占比 <b>' + posHigher + '</b> 更高：'
        + Math.max(posA, posB).toFixed(1) + '% 对 ' + Math.min(posA, posB).toFixed(1)
        + '%，相差 ' + Math.abs(posA - posB).toFixed(1) + ' 个百分点。');
    }
    if (Math.abs(negA - negB) >= 1) {
      var negWorse = negA > negB ? labelA : labelB;
      items.push('负面占比 <b>' + negWorse + '</b> 更高：'
        + Math.max(negA, negB).toFixed(1) + '% 对 ' + Math.min(negA, negB).toFixed(1)
        + '%，需要重点排查该批评论的投诉点。');
    }
    if (Math.abs(neuA - neuB) >= 1) {
      var neuHigher = neuA > neuB ? labelA : labelB;
      items.push('中性占比 <b>' + neuHigher + '</b> 更高（'
        + Math.max(neuA, neuB).toFixed(1) + '%），表态不明确的评论更多，'
        + '可结合关键词判断是否存在隐含不满。');
    }

    var confA = left.stats && left.stats.avgConfidence !== null
      && left.stats.avgConfidence !== undefined ? Number(left.stats.avgConfidence) * 100 : null;
    var confB = right.stats && right.stats.avgConfidence !== null
      && right.stats.avgConfidence !== undefined ? Number(right.stats.avgConfidence) * 100 : null;
    if (confA !== null && confB !== null && Math.abs(confA - confB) >= 1) {
      var confHigher = confA > confB ? labelA : labelB;
      items.push('平均置信度 <b>' + confHigher + '</b> 更高（'
        + Math.max(confA, confB).toFixed(1) + '% 对 ' + Math.min(confA, confB).toFixed(1)
        + '%），模型对该任务判定更笃定。');
    }

    var rateA = left.quality && left.quality.reviewedCount
      ? Number(left.quality.agreementRate || 0) * 100 : null;
    var rateB = right.quality && right.quality.reviewedCount
      ? Number(right.quality.agreementRate || 0) * 100 : null;
    if (rateA !== null && rateB !== null && Math.abs(rateA - rateB) >= 1) {
      var rateHigher = rateA > rateB ? labelA : labelB;
      items.push('复核一致率 <b>' + rateHigher + '</b> 更高（'
        + Math.max(rateA, rateB).toFixed(1) + '% 对 ' + Math.min(rateA, rateB).toFixed(1)
        + '%），该任务的人工改判更少。');
    }

    if (!items.length) {
      items.push('两个任务在情感分布、置信度与复核质量上没有明显差异。');
    }

    $('compareSummary').innerHTML = ''
      + '<p class="compare-summary__title">对比结论</p>'
      + '<ul class="compare-summary__list">'
      + items.map(function (text) {
        return '<li>' + text + '</li>';
      }).join('')
      + '</ul>';
  }

  /**
   * 渲染核心指标对比表（差异按 B − A 计算）。
   *
   * @param {object} left  A 任务数据
   * @param {object} right B 任务数据
   * @param {string} nameA A 任务名
   * @param {string} nameB B 任务名
   */
  function renderCompareTable(left, right, nameA, nameB) {
    var rows = [
      {
        label: '评论总数',
        a: Number(left.stats.totalCount || 0),
        b: Number(right.stats.totalCount || 0),
        format: 'count',
        better: null
      },
      {
        label: '正面占比',
        a: compareRatio(left.stats, 'positiveCount'),
        b: compareRatio(right.stats, 'positiveCount'),
        format: 'percent',
        better: 'high'
      },
      {
        label: '负面占比',
        a: compareRatio(left.stats, 'negativeCount'),
        b: compareRatio(right.stats, 'negativeCount'),
        format: 'percent',
        better: 'low'
      },
      {
        label: '中性占比',
        a: compareRatio(left.stats, 'neutralCount'),
        b: compareRatio(right.stats, 'neutralCount'),
        format: 'percent',
        better: null
      },
      {
        label: '平均置信度',
        a: toRatioOrNull(left.stats.avgConfidence),
        b: toRatioOrNull(right.stats.avgConfidence),
        format: 'percent',
        better: 'high'
      },
      {
        label: '低置信度占比',
        a: toRatioOrNull(left.confidence.belowThresholdRatio),
        b: toRatioOrNull(right.confidence.belowThresholdRatio),
        format: 'percent',
        better: 'low'
      },
      {
        label: '待人工复核',
        a: Number(left.stats.reviewCount || 0),
        b: Number(right.stats.reviewCount || 0),
        format: 'count',
        better: 'low'
      },
      {
        label: '已人工复核',
        a: Number(left.quality.reviewedCount || 0),
        b: Number(right.quality.reviewedCount || 0),
        format: 'count',
        better: null
      },
      {
        label: '复核一致率',
        a: left.quality.reviewedCount ? toRatioOrNull(left.quality.agreementRate) : null,
        b: right.quality.reviewedCount ? toRatioOrNull(right.quality.agreementRate) : null,
        format: 'percent',
        better: 'high'
      }
    ];

    var head = '<thead><tr><th>指标</th>'
      + '<th class="head-a"><span class="compare-table__name" title="' + escapeHtml(nameA)
      + '">' + escapeHtml(nameA) + '</span></th>'
      + '<th class="head-b"><span class="compare-table__name" title="' + escapeHtml(nameB)
      + '">' + escapeHtml(nameB) + '</span></th>'
      + '<th>差异（B − A）</th></tr></thead>';

    var body = '<tbody>' + rows.map(function (row) {
      var aText = formatCompareValue(row.a, row.format);
      var bText = formatCompareValue(row.b, row.format);
      var deltaHtml = '<span class="delta">—</span>';

      if (row.a !== null && row.b !== null) {
        var diff = row.format === 'percent' ? (row.b - row.a) * 100 : row.b - row.a;
        var sign = diff > 0 ? '+' : '';
        var suffix = row.format === 'percent' ? ' pt' : '';
        var cls = diff > 0 ? 'up' : (diff < 0 ? 'down' : '');
        deltaHtml = '<span class="delta ' + cls + '">' + sign + diff.toFixed(1) + suffix + '</span>';
      }

      var aCls = '';
      var bCls = '';
      if (row.a !== null && row.b !== null && row.better) {
        if (row.better === 'high') {
          aCls = row.a > row.b ? ' class="better"' : '';
          bCls = row.b > row.a ? ' class="better"' : '';
        } else {
          aCls = row.a < row.b ? ' class="better"' : '';
          bCls = row.b < row.a ? ' class="better"' : '';
        }
      }

      return '<tr><td>' + escapeHtml(row.label) + '</td>'
        + '<td' + aCls + '>' + aText + '</td>'
        + '<td' + bCls + '>' + bText + '</td>'
        + '<td>' + deltaHtml + '</td></tr>';
    }).join('') + '</tbody>';

    $('compareTable').innerHTML = head + body;
    $('compareTableAside').textContent = '绿色为更优；差异按 B − A 计算';
  }

  /**
   * 把 0～1 的占比字段转为数字，非法值返回 null。
   * @param {*} value 原始值
   * @returns {number|null} 占比或 null
   */
  function toRatioOrNull(value) {
    if (value === null || value === undefined || value === '') {
      return null;
    }
    return Number(value);
  }

  /**
   * 按类型格式化对比值。
   * @param {*}      value  数值
   * @param {string} format count / percent
   * @returns {string} 展示文案
   */
  function formatCompareValue(value, format) {
    if (value === null || value === undefined) {
      return '—';
    }
    if (format === 'percent') {
      return (Number(value) * 100).toFixed(1) + '%';
    }
    return formatNumber(value);
  }

  /**
   * 渲染关键词差异：A 独有 / 共有 / B 独有。
   *
   * @param {object} left  A 任务数据
   * @param {object} right B 任务数据
   * @param {string} nameA A 任务名
   * @param {string} nameB B 任务名
   */
  function renderCompareWords(left, right, nameA, nameB) {
    var wordsA = (left.keywords || []).map(function (item) {
      return item.word;
    });
    var wordsB = (right.keywords || []).map(function (item) {
      return item.word;
    });
    var setB = {};
    wordsB.forEach(function (word) {
      setB[word] = true;
    });
    var setA = {};
    wordsA.forEach(function (word) {
      setA[word] = true;
    });

    var onlyA = wordsA.filter(function (word) {
      return !setB[word];
    });
    var onlyB = wordsB.filter(function (word) {
      return !setA[word];
    });
    var shared = wordsA.filter(function (word) {
      return setB[word];
    });

    var column = function (title, name, words, cls, emptyText) {
      var chips = words.length
        ? words.map(function (word) {
          return '<span class="compare-word ' + cls + '">' + escapeHtml(word) + '</span>';
        }).join('')
        : '<span class="word-diff__empty">' + escapeHtml(emptyText) + '</span>';
      return '<div class="word-diff__col">'
        + '  <div class="word-diff__head"><span>' + escapeHtml(title) + '</span>'
        + '    <b>' + words.length + '</b></div>'
        + '  <div class="word-diff__list">' + chips + '</div>'
        + '</div>';
    };

    $('compareWords').innerHTML = ''
      + column('仅 ' + nameA + ' 出现', nameA, onlyA, 'compare-word--a', '没有独有关键词')
      + column('两个任务共有', '', shared, 'is-shared', '没有共同关键词')
      + column('仅 ' + nameB + ' 出现', nameB, onlyB, 'compare-word--b', '没有独有关键词');
  }

  /* ==========================================================================
     事件绑定
     ========================================================================== */

  /**
   * 输入防抖。
   * @param {Function} fn 目标函数
   * @param {number} delay 延迟毫秒
   * @returns {Function} 包装后的函数
   */
  function debounce(fn, delay) {
    var timer = null;
    return function () {
      var args = arguments;
      clearTimeout(timer);
      timer = setTimeout(function () {
        fn.apply(null, args);
      }, delay);
    };
  }

  /**
   * 绑定全部交互事件。
   */
  function bindEvents() {
    /* ---- 登录 ---- */
    $('authForm').addEventListener('submit', handleAuthSubmit);
    $('authSwitch').addEventListener('click', function () {
      setAuthMode(state.authMode === 'login' ? 'register' : 'login');
    });
    $('logoutBtn').addEventListener('click', function () {
      logout(false);
    });

    /* ---- 视图切换 ---- */
    $('railNav').addEventListener('click', function (event) {
      var button = event.target.closest('.rail__nav-btn');
      if (button) {
        setView(button.dataset.view, true);
      }
    });

    /* ---- 解析报告 ---- */
    $('reportModal').addEventListener('click', function (event) {
      if (event.target.closest('[data-close-report]')) {
        closeParseReport();
      }
    });
    $('downloadBackupBtn').addEventListener('click', downloadBackup);

    /* ---- 个人中心 ---- */
    $('profileBtn').addEventListener('click', openProfile);
    // 点遮罩或关闭按钮关闭弹窗
    $('profileModal').addEventListener('click', function (event) {
      if (event.target.closest('[data-close-profile]')) {
        closeProfile();
      }
    });
    $('passwordForm').addEventListener('submit', handlePasswordSubmit);
    $('profileLogoutBtn').addEventListener('click', function () {
      closeProfile();
      logout(false);
    });
    // Esc 关闭个人中心 / 解析报告
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') {
        closeProfile();
        closeParseReport();
      }
    });

    /* ---- 上传 ---- */
    var dropzone = $('dropzone');
    var fileInput = $('fileInput');

    dropzone.addEventListener('click', function () {
      fileInput.click();
    });
    dropzone.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        fileInput.click();
      }
    });
    fileInput.addEventListener('change', function () {
      handleFile(fileInput.files[0]);
      // 清空以便重复选择同一文件时仍能触发 change
      fileInput.value = '';
    });

    ['dragenter', 'dragover'].forEach(function (type) {
      dropzone.addEventListener(type, function (event) {
        event.preventDefault();
        dropzone.classList.add('is-dragging');
      });
    });
    ['dragleave', 'drop'].forEach(function (type) {
      dropzone.addEventListener(type, function (event) {
        event.preventDefault();
        dropzone.classList.remove('is-dragging');
      });
    });
    dropzone.addEventListener('drop', function (event) {
      var files = event.dataTransfer && event.dataTransfer.files;
      if (files && files.length) {
        handleFile(files[0]);
      }
    });

    /* ---- 智能输入 ---- */
    $('smartInput').addEventListener('input', updateSmartHint);
    $('smartSubmit').addEventListener('click', submitSmartInput);
    // Ctrl / Cmd + Enter 快速提交，符合粘贴后直接发送的习惯
    $('smartInput').addEventListener('keydown', function (event) {
      if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
        event.preventDefault();
        submitSmartInput();
      }
    });
    updateSmartHint();

    /* ---- 任务列表 ---- */
    $('taskList').addEventListener('click', function (event) {
      var check = event.target.closest('[data-task-check]');
      if (check) {
        toggleTaskSelection(Number(check.dataset.taskCheck), check.checked);
        return;
      }
      var retry = event.target.closest('[data-task-retry]');
      if (retry) {
        retryTask(Number(retry.dataset.taskRetry));
        return;
      }
      var open = event.target.closest('[data-task-id]');
      if (open) {
        selectTask(Number(open.dataset.taskId));
      }
    });
    $('taskSearch').addEventListener('input', debounce(function () {
      // 搜索条件变化时回到第一页
      state.taskQuery.pageNum = 1;
      loadTasks();
    }, 320));

    // 按任务状态筛选（FR-BIZ-22）
    $('taskStatus').addEventListener('change', function () {
      state.taskQuery.pageNum = 1;
      loadTasks();
    });

    // 按创建时间范围筛选任务（FR-BIZ-22）
    ['taskDateStart', 'taskDateEnd'].forEach(function (id) {
      $(id).addEventListener('change', function () {
        state.taskQuery.pageNum = 1;
        loadTasks();
      });
    });

    /* ---- 任务列表分页 ---- */
    $('taskPager').addEventListener('click', function (event) {
      var button = event.target.closest('[data-task-page]');
      if (!button || button.disabled) {
        return;
      }
      var query = state.taskQuery;
      if (button.dataset.taskPage === 'prev') {
        query.pageNum = Math.max(1, query.pageNum - 1);
      } else {
        query.pageNum = Math.min(query.pages, query.pageNum + 1);
      }
      loadTasks();
    });

    /* ---- 任务操作 ---- */
    $('runBtn').addEventListener('click', runCurrentTask);
    $('cancelBtn').addEventListener('click', cancelCurrentTask);
    $('deleteBtn').addEventListener('click', deleteCurrentTask);
    $('exportBtn').addEventListener('click', exportCurrentTask);
    $('reportBtn').addEventListener('click', exportReport);
    $('renameBtn').addEventListener('click', openRename);

    /* ---- 任务对比 ---- */
    $('compareRefreshBtn').addEventListener('click', loadCompareOptions);
    $('compareRunBtn').addEventListener('click', runCompare);

    /* ---- 网页正文确认弹窗 ---- */
    document.querySelectorAll('[data-close-preview]').forEach(function (element) {
      element.addEventListener('click', closePagePreview);
    });
    $('previewConfirmBtn').addEventListener('click', confirmPagePreview);
    $('previewRetryBtn').addEventListener('click', retryPagePreview);

    /* ---- 任务批量操作 ---- */
    $('taskBatchDeleteBtn').addEventListener('click', batchDeleteTasks);
    $('taskBatchClearBtn').addEventListener('click', clearTaskSelection);

    /* ---- 任务重命名弹窗 ---- */
    document.querySelectorAll('[data-close-rename]').forEach(function (element) {
      element.addEventListener('click', closeRename);
    });
    $('renameSubmitBtn').addEventListener('click', submitRename);
    $('renameInput').addEventListener('keydown', function (event) {
      if (event.key === 'Enter') {
        event.preventDefault();
        submitRename();
      }
    });

    /* ---- 图表联动：点词云筛关键词、点饼图筛情感 ---- */
    charts.onWordClick(applyKeywordFilter);
    charts.onPieClick(applySentimentFilter);

    /* ---- 词云情感筛选 ---- */
    $('cloudSeg').addEventListener('click', function (event) {
      var button = event.target.closest('.seg__btn');
      if (!button || !state.currentTask) {
        return;
      }
      $('cloudSeg').querySelectorAll('.seg__btn').forEach(function (item) {
        item.classList.toggle('is-active', item === button);
      });
      state.cloudSentiment = button.dataset.sentiment;
      loadKeywords(state.currentTask.taskId);
    });

    /* ---- 结果表格筛选 ---- */
    $('sentimentFilter').addEventListener('change', function () {
      if (!state.currentTask) {
        return;
      }
      state.resultQuery.sentiment = $('sentimentFilter').value;
      state.resultQuery.pageNum = 1;
      loadResults(state.currentTask.taskId);
    });
    // 复核状态筛选：只看待复核 / 只看已复核
    $('reviewFilter').addEventListener('change', function () {
      if (!state.currentTask) {
        return;
      }
      var reviewValue = $('reviewFilter').value;
      // 1=只看待复核，0=只看已人工复核；两者是不同字段，不能混用
      state.resultQuery.needReview = reviewValue === '1' ? '1' : '';
      state.resultQuery.reviewed = reviewValue === '0' ? '1' : '';
      state.resultQuery.pageNum = 1;
      loadResults(state.currentTask.taskId);
    });
    // 置信度排序：首次点击升序，再次点击降序
    $('confidenceSortBtn').addEventListener('click', function () {
      if (!state.currentTask) {
        return;
      }
      var query = state.resultQuery;
      query.sortBy = 'confidence';
      query.sortOrder = query.sortOrder === 'asc' ? 'desc' : 'asc';
      query.pageNum = 1;
      updateSortArrow();
      loadResults(state.currentTask.taskId);
    });
    // 复核列按钮：委托到 tbody，点击进入人工复核弹窗
    $('resultBody').addEventListener('click', function (event) {
      // 批量勾选
      var check = event.target.closest('[data-result-check]');
      if (check) {
        var resultId = Number(check.dataset.resultCheck);
        if (check.checked) {
          state.selectedResultIds[resultId] = true;
        } else {
          delete state.selectedResultIds[resultId];
        }
        updateResultBatchBar();
        return;
      }
      // 长评论展开 / 收起
      var toggle = event.target.closest('.cell-content__toggle');
      if (toggle) {
        var text = toggle.parentNode.querySelector('.cell-content__text');
        var clamped = text.classList.toggle('is-clamp');
        toggle.textContent = clamped ? '展开' : '收起';
        return;
      }
      // 关键词胶囊：点击即按该词筛选
      var chip = event.target.closest('[data-keyword]');
      if (chip) {
        applyKeywordFilter(chip.dataset.keyword);
        return;
      }
      var button = event.target.closest('.review-tag');
      if (button && !button.disabled) {
        openReview(Number(button.dataset.resultId));
      }
    });

    /* ---- 结果批量复核 ---- */
    $('resultCheckAll').addEventListener('change', function () {
      var checked = $('resultCheckAll').checked;
      state.selectedResultIds = {};
      if (checked) {
        (state.resultRows || []).forEach(function (row) {
          state.selectedResultIds[row.resultId] = true;
        });
      }
      renderResultRows(state.resultRows);
    });
    $('batchReviewBtn').addEventListener('click', submitBatchReview);
    $('batchClearBtn').addEventListener('click', clearResultSelection);

    /* ---- 人工复核弹窗 ---- */
    document.querySelectorAll('[data-close-review]').forEach(function (element) {
      element.addEventListener('click', closeReview);
    });
    $('reviewOptions').addEventListener('click', function (event) {
      var button = event.target.closest('.review-option');
      if (button) {
        selectReviewSentiment(button.dataset.sentiment);
      }
    });
    $('reviewSubmitBtn').addEventListener('click', function () {
      submitReview(false);
    });
    $('reviewUndoBtn').addEventListener('click', function () {
      submitReview(true);
    });
    // Esc 关闭弹窗
    document.addEventListener('keydown', function (event) {
      if (event.key !== 'Escape') {
        return;
      }
      if (!$('reviewModal').hidden) {
        closeReview();
      }
      if (!$('columnModal').hidden) {
        closeColumnPicker();
      }
      if (!$('renameModal').hidden) {
        closeRename();
      }
      if (!$('previewModal').hidden) {
        closePagePreview();
      }
    });

    /* ---- 评论列人工指定 ---- */
    document.querySelectorAll('[data-close-column]').forEach(function (element) {
      element.addEventListener('click', closeColumnPicker);
    });
    $('columnOptions').addEventListener('click', function (event) {
      var label = event.target.closest('.column-option');
      if (!label) {
        return;
      }
      var input = label.querySelector('input');
      if (!input) {
        return;
      }
      state.columnSelection = Number(input.value);
      $('columnOptions').querySelectorAll('.column-option').forEach(function (item) {
        item.classList.toggle('is-active', item === label);
      });
    });
    $('columnSubmitBtn').addEventListener('click', submitColumn);
    // 置信度区间筛选（FR-BIZ-20）：两个输入框变更均立即查询
    ['confidenceMin', 'confidenceMax'].forEach(function (id) {
      $(id).addEventListener('change', function () {
        if (!state.currentTask) {
          return;
        }
        state.resultQuery.pageNum = 1;
        loadResults(state.currentTask.taskId);
      });
    });
    $('resultSearch').addEventListener('input', debounce(function () {
      if (!state.currentTask) {
        return;
      }
      state.resultQuery.keyword = $('resultSearch').value.trim();
      state.resultQuery.pageNum = 1;
      loadResults(state.currentTask.taskId);
    }, 320));

    /* ---- 分页 ---- */
    $('pager').addEventListener('click', function (event) {
      var button = event.target.closest('.page-btn');
      if (button && !button.disabled) {
        goPage(button.dataset.page);
      }
    });

    /* ---- 数据看板 ---- */
    $('boardRefreshBtn').addEventListener('click', loadDashboard);
    $('boardRecent').addEventListener('click', function (event) {
      var button = event.target.closest('[data-task-id]');
      if (button) {
        selectTask(Number(button.dataset.taskId));
      }
    });

    /* ---- 系统设置 ---- */
    $('settingsRefreshBtn').addEventListener('click', loadSettings);
    $('settingsForm').addEventListener('submit', handleSettingsSubmit);

    /* ---- 窗口尺寸变化 ---- */
    window.addEventListener('resize', debounce(function () {
      charts.resize();
    }, 160));
  }

  /* ==========================================================================
     启动
     ========================================================================== */

  /**
   * 初始化入口。
   */
  async function init() {
    bindEvents();
    setAuthMode('login');

    // 登录态以服务端会话为准，刷新页面后向 /api/user/me 校验
    try {
      state.user = await api.get('/api/user/me');
      showApp();
    } catch (error) {
      state.user = null;
      showLogin();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
