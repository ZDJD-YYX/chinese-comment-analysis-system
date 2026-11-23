/**
 * Motion.Lab 动效调度层
 * ----------------------------------------------------------------------------
 * 只做三件事：
 *   1. 给静态元素补上 anim-* 类（不改变原有结构与业务类名）；
 *   2. 用事件委托 / MutationObserver 接管动态渲染出来的列表与状态；
 *   3. 提供滚动进度、滚动揭示、数字滚动、磁吸、倾斜、波纹、粒子等 JS 动效。
 *
 * 全部逻辑封装在 IIFE 内，不向 window 挂载任何变量。
 * 当系统开启"减少动态效果"时，除滚动进度外全部跳过。
 */
(function () {
  'use strict';

  var reduceMotion = !!(window.matchMedia
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

  var raf = window.requestAnimationFrame
    ? window.requestAnimationFrame.bind(window)
    : function (fn) { return setTimeout(fn, 16); };

  /** 查询并转为数组，便于 forEach */
  function qsa(selector, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(selector));
  }

  function $(id) {
    return document.getElementById(id);
  }

  function addClass(el, className) {
    if (el && el.classList) {
      el.classList.add(className);
    }
  }

  /* ==========================================================================
     1. 静态元素装饰
     ========================================================================== */

  function decorateButtons(root) {
    qsa('.btn--primary, .dropzone', root).forEach(function (el) {
      addClass(el, 'anim-lift');
    });

    qsa('.btn--ghost, .rail__logout, .seg__btn, .page-btn', root).forEach(function (el) {
      addClass(el, 'anim-hover-color');
      addClass(el, 'anim-hover-scale');
    });

    qsa('.dropzone__icon', root).forEach(function (el) {
      addClass(el, 'anim-icon-spin');
    });
  }

  function decorateStatic() {
    decorateButtons(document);

    addClass($('authSubmit'), 'anim-magnetic');
    addClass(document.querySelector('.auth-card'), 'anim-zoom-bounce');

    qsa('.chart').forEach(function (el) {
      addClass(el, 'anim-chart');
    });
  }

  /* ==========================================================================
     2. 滚动进度条
     ========================================================================== */

  function initScrollProgress() {
    var host = document.querySelector('.anim-scroll-progress');
    if (!host) {
      return;
    }
    var bar = host.firstElementChild;
    var main = document.querySelector('.main');
    var ticking = false;

    function update() {
      ticking = false;
      var appView = $('appView');
      // 窄屏下 .main 会改为 overflow:visible，由整页滚动接管，这里动态判断真正的滚动源
      var mainScrollable = !!(main
        && window.getComputedStyle(main).overflowY !== 'visible'
        && main.scrollHeight > main.clientHeight + 8);
      var useMain = !!(mainScrollable && appView && !appView.hidden);
      var max = useMain
        ? main.scrollHeight - main.clientHeight
        : document.documentElement.scrollHeight - window.innerHeight;
      var top = useMain ? main.scrollTop : (window.pageYOffset || document.documentElement.scrollTop);
      var progress = max > 8 ? Math.min(1, Math.max(0, top / max)) : 0;

      bar.style.width = (progress * 100).toFixed(2) + '%';
      host.classList.toggle('is-active', progress > 0.002);
    }

    function onScroll() {
      if (!ticking) {
        ticking = true;
        raf(update);
      }
    }

    window.addEventListener('scroll', onScroll, { passive: true });
    if (main) {
      main.addEventListener('scroll', onScroll, { passive: true });
    }
    window.addEventListener('resize', onScroll);

    // 登录 ↔ 工作台切换后滚动容器会变化，重新计算一次
    ['loginView', 'appView'].forEach(function (id) {
      var view = $(id);
      if (view) {
        new MutationObserver(onScroll).observe(view, {
          attributes: true,
          attributeFilter: ['hidden']
        });
      }
    });

    update();
  }

  /* ==========================================================================
     3. 滚动揭示
     ========================================================================== */

  function initReveal() {
    if (reduceMotion || !('IntersectionObserver' in window)) {
      return;
    }

    var targets = qsa([
      '.auth__intro',
      '.auth__facts',
      '.auth__panel',
      '.taskbar',
      '.empty',
      '.grid',
      '.card--table'
    ].join(','));

    if (!targets.length) {
      return;
    }

    targets.forEach(function (el) {
      el.classList.add('anim-reveal');
    });

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-in');
          // 卡片网格进入视口时，再启动内部卡片的错落入场
          if (entry.target.classList.contains('grid')) {
            applyStagger(entry.target, ':scope > .card', false);
          }
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -6% 0px' });

    targets.forEach(function (el) {
      observer.observe(el);
    });
  }

  /* ==========================================================================
     4. 列表错深入场
     ========================================================================== */

  /**
   * @param {HTMLElement} container 容器
   * @param {string} selector 子项选择器
   * @param {boolean} once 是否只在首次渲染时播放
   */
  function applyStagger(container, selector, once) {
    if (!container || reduceMotion) {
      return;
    }

    container.classList.add('anim-stagger');

    function mark() {
      var items = qsa(selector, container);
      items.forEach(function (el, index) {
        if (!el.style.getPropertyValue('--anim-index')) {
          el.style.setProperty('--anim-index', String(Math.min(index, 12)));
        }
      });
    }

    mark();

    if (once) {
      var timer = null;
      var arm = function () {
        if (timer || !container.querySelector(selector)) {
          return;
        }
        // 首次渲染完成后关闭重复入场，避免轮询刷新导致列表反复闪动
        timer = setTimeout(function () {
          container.classList.add('is-done');
        }, 1200);
      };
      arm();
      new MutationObserver(function () {
        mark();
        arm();
      }).observe(container, { childList: true });
    } else {
      new MutationObserver(mark).observe(container, { childList: true });
    }
  }

  function initStagger() {
    applyStagger($('taskList'), '.task', true);
    applyStagger($('resultBody'), 'tr', false);
    applyStagger($('rankList'), '.rank__item', false);
    applyStagger(document.querySelector('.auth__facts'), '.auth__fact', false);

    // 概览读数在登录后才能看到，等切换进工作台再播放错落入场
    var appView = $('appView');
    var started = false;
    if (appView) {
      var start = function () {
        if (started || appView.hidden) {
          return;
        }
        started = true;
        applyStagger(document.querySelector('.stats'), '.stat', false);
        applyStagger($('metrics'), '.metrics__item', false);
      };
      start();
      new MutationObserver(start).observe(appView, {
        attributes: true,
        attributeFilter: ['hidden']
      });
    }
  }

  /* ==========================================================================
     5. 按钮波纹
     ========================================================================== */

  function initRipple() {
    if (reduceMotion) {
      return;
    }

    document.addEventListener('click', function (event) {
      var button = event.target.closest('.btn, .page-btn, .seg__btn');
      if (!button || button.disabled) {
        return;
      }

      var rect = button.getBoundingClientRect();
      var size = Math.max(rect.width, rect.height) * 0.6;
      var ripple = document.createElement('span');
      ripple.className = 'anim-ripple';
      ripple.style.width = size + 'px';
      ripple.style.height = size + 'px';
      ripple.style.left = (event.clientX - rect.left - size / 2) + 'px';
      ripple.style.top = (event.clientY - rect.top - size / 2) + 'px';
      button.appendChild(ripple);
      setTimeout(function () {
        ripple.remove();
      }, 620);
    });
  }

  /* ==========================================================================
     6. 磁吸按钮（登录）
     ========================================================================== */

  function initMagnetic() {
    if (reduceMotion) {
      return;
    }

    var button = $('authSubmit');
    if (!button) {
      return;
    }

    var radius = 80;
    var strength = 0.3;

    document.addEventListener('mousemove', function (event) {
      if (!button.offsetParent) {
        return;
      }
      var rect = button.getBoundingClientRect();
      var dx = event.clientX - (rect.left + rect.width / 2);
      var dy = event.clientY - (rect.top + rect.height / 2);

      if (Math.sqrt(dx * dx + dy * dy) < radius) {
        button.style.transform = 'translate(' + (dx * strength).toFixed(1) + 'px, '
          + (dy * strength).toFixed(1) + 'px)';
      } else if (button.style.transform) {
        button.style.transform = '';
      }
    });
  }

  /* ==========================================================================
     7. 任务卡片 3D 倾斜
     ========================================================================== */

  function initTilt() {
    if (reduceMotion) {
      return;
    }

    var list = $('taskList');
    if (!list) {
      return;
    }

    var active = null;

    list.addEventListener('pointermove', function (event) {
      var card = event.target.closest('.task');
      if (!card) {
        return;
      }

      if (active && active !== card) {
        active.style.transform = '';
      }
      active = card;
      card.classList.add('anim-tilt');

      var rect = card.getBoundingClientRect();
      var x = (event.clientX - rect.left) / rect.width - 0.5;
      var y = (event.clientY - rect.top) / rect.height - 0.5;

      card.style.transform = 'perspective(800px) rotateY(' + (x * 24).toFixed(2)
        + 'deg) rotateX(' + (-y * 24).toFixed(2) + 'deg)';
      card.style.setProperty('--anim-mx', ((x + 0.5) * 100).toFixed(1) + '%');
      card.style.setProperty('--anim-my', ((y + 0.5) * 100).toFixed(1) + '%');
    });

    list.addEventListener('pointerout', function (event) {
      var card = event.target.closest('.task');
      if (card && !card.contains(event.relatedTarget)) {
        card.style.transform = '';
        if (active === card) {
          active = null;
        }
      }
    });
  }

  /* ==========================================================================
     8. 情感计数
     ========================================================================== */

  // 情感概览的正/负/中性条数直接由 app.js 的 setStat 写入，不再做数字滚动动画。
  // 原因：切换任务时先清零再写入真实值，动画若被中断会让读数停在 0，
  // 与占比、饼图不一致；这三项是可核对的关键数字，稳定优先于动效。

  /* ==========================================================================
     9. 轻提示与分析完成通知
     ========================================================================== */

  var pendingExport = false;

  function initToasts() {
    var host = $('toastHost');
    if (!host) {
      return;
    }

    new MutationObserver(function (mutations) {
      mutations.forEach(function (mutation) {
        Array.prototype.forEach.call(mutation.addedNodes, function (node) {
          if (node.nodeType !== 1 || !node.classList.contains('toast')) {
            return;
          }
          addClass(node, 'anim-toast');

          if (pendingExport && node.classList.contains('toast--ok')) {
            pendingExport = false;
            burstAt($('exportBtn'));
          }
        });
      });
    }).observe(host, { childList: true });
  }

  function showAnalysisToast() {
    var toast = document.createElement('div');
    toast.className = 'anim-analysis-toast';
    toast.innerHTML = ''
      + '<span class="anim-analysis-toast__icon" aria-hidden="true">'
      + '  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
      + '       stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">'
      + '    <path d="M20 6 9 17l-5-5"/>'
      + '  </svg>'
      + '</span>'
      + '<span class="anim-analysis-toast__text"><b>分析完成</b><span>结果与图表已更新</span></span>';

    document.body.appendChild(toast);
    setTimeout(function () {
      toast.classList.add('is-leaving');
      setTimeout(function () {
        toast.remove();
      }, 320);
    }, 3400);
  }

  function statusOfPill(pill) {
    var match = /pill--(SUCCESS|RUNNING|PENDING|FAILED|CANCELED)/.exec(pill.className);
    return match ? match[1] : '';
  }

  function initCompletionWatcher() {
    var pill = $('taskStatusPill');
    if (!pill) {
      return;
    }

    var last = statusOfPill(pill);

    new MutationObserver(function () {
      var status = statusOfPill(pill);
      if (status === last) {
        return;
      }
      // 仅当任务从"运行中"变为"已完成"时提示，避免初次加载就弹通知
      if (status === 'SUCCESS' && last === 'RUNNING') {
        showAnalysisToast();

        var activeCard = document.querySelector('.task.is-active');
        if (activeCard && !reduceMotion) {
          activeCard.classList.add('anim-tada');
          activeCard.addEventListener('animationend', function () {
            activeCard.classList.remove('anim-tada');
          }, { once: true });
          // 兜底：动画被其他规则阻断时也能清理类名
          setTimeout(function () {
            activeCard.classList.remove('anim-tada');
          }, 1200);
        }
      }
      last = status;
    }).observe(pill, {
      attributes: true,
      attributeFilter: ['class'],
      childList: true,
      characterData: true,
      subtree: true
    });
  }

  /* ==========================================================================
     10. 登录失败反馈
     ========================================================================== */

  function initValidationFeedback() {
    var error = $('authError');
    var card = document.querySelector('.auth-card');
    if (!error || !card) {
      return;
    }

    var inputs = [$('authUsername'), $('authPassword')];

    function setErrorState(on) {
      inputs.forEach(function (input) {
        if (input) {
          input.classList.toggle('anim-error', on);
        }
      });
    }

    new MutationObserver(function () {
      var visible = !error.hidden && (error.textContent || '').trim().length > 0;
      if (!visible) {
        setErrorState(false);
        return;
      }

      setErrorState(true);

      if (!reduceMotion) {
        card.classList.remove('anim-shake');
        void card.offsetWidth;
        card.classList.add('anim-shake');

        inputs.forEach(function (input) {
          if (input) {
            input.classList.remove('anim-shake');
            void input.offsetWidth;
            input.classList.add('anim-shake');
          }
        });

        error.classList.remove('anim-flash');
        void error.offsetWidth;
        error.classList.add('anim-flash');
      }

      setTimeout(function () {
        setErrorState(false);
      }, 1800);
    }).observe(error, {
      attributes: true,
      attributeFilter: ['hidden'],
      childList: true,
      characterData: true,
      subtree: true
    });
  }

  /* ==========================================================================
     11. 删除 / 导出反馈
     ========================================================================== */

  function initDeleteFeedback() {
    var button = $('deleteBtn');
    if (!button) {
      return;
    }

    button.addEventListener('pointerdown', function () {
      if (button.disabled) {
        return;
      }

      if (!reduceMotion) {
        button.classList.remove('anim-shake');
        void button.offsetWidth;
        button.classList.add('anim-shake');
      }

      var card = document.querySelector('.task.is-active');
      if (card && !reduceMotion) {
        card.classList.add('anim-removing');
        // 用户在确认框点了取消时，把卡片恢复
        setTimeout(function () {
          card.classList.remove('anim-removing');
        }, 1400);
      }
    });
  }

  function burstAt(button) {
    if (reduceMotion || !button) {
      return;
    }

    var rect = button.getBoundingClientRect();
    if (!rect.width) {
      return;
    }

    var host = document.createElement('div');
    host.setAttribute('aria-hidden', 'true');
    host.style.cssText = 'position:fixed;left:0;top:0;width:0;height:0;z-index:70;pointer-events:none;';
    document.body.appendChild(host);

    var originX = rect.left + rect.width / 2;
    var originY = rect.top + rect.height / 2;
    var count = 20;

    for (var i = 0; i < count; i++) {
      var particle = document.createElement('span');
      var angle = (i / count) * Math.PI * 2;
      var distance = 40 + Math.random() * 34;

      particle.className = 'anim-burst-particle';
      particle.style.left = originX + 'px';
      particle.style.top = originY + 'px';
      particle.style.background = 'hsl(' + Math.floor(Math.random() * 360) + ' 90% 62%)';
      host.appendChild(particle);

      (function (node, dx, dy) {
        raf(function () {
          raf(function () {
            node.style.transform = 'translate(' + dx + 'px, ' + dy + 'px) scale(0)';
            node.style.opacity = '0';
          });
        });
      })(particle, Math.cos(angle) * distance, Math.sin(angle) * distance);
    }

    setTimeout(function () {
      host.remove();
    }, 760);
  }

  function initExportBurst() {
    var button = $('exportBtn');
    if (!button) {
      return;
    }

    button.addEventListener('click', function () {
      if (!button.disabled) {
        pendingExport = true;
        // 10 秒内没有出现成功提示就取消标记
        setTimeout(function () {
          pendingExport = false;
        }, 10000);
      }
    });
  }

  /* ==========================================================================
     12. 分析执行中：旋转图标 + 进度文字打字机
     ========================================================================== */

  function typeText(element, text, speed) {
    if (!element || reduceMotion) {
      return;
    }
    var index = 0;
    element.textContent = '';
    var timer = setInterval(function () {
      index++;
      element.textContent = text.slice(0, index);
      if (index >= text.length) {
        clearInterval(timer);
      }
    }, speed);
  }

  function initRunState() {
    var runBar = $('runBar');
    if (!runBar) {
      return;
    }

    var label = $('runLabel');
    var typed = false;

    function sync() {
      if (!runBar.hidden) {
        runBar.classList.add('anim-running');

        if (!typed && label) {
          typed = true;
          typeText(label, label.textContent || '正在分析评论情感', 45);
        }
      } else {
        runBar.classList.remove('anim-running');
        typed = false;
      }
    }

    new MutationObserver(sync).observe(runBar, {
      attributes: true,
      attributeFilter: ['hidden']
    });

    // 兼容初始就可见的情况（例如刷新后直接恢复运行中任务）
    sync();
  }

  /* ==========================================================================
     13. 上传加载态
     ========================================================================== */

  function initUploadSpinner() {
    var meter = $('uploadMeter');
    var dropzone = $('dropzone');
    if (!meter || !dropzone) {
      return;
    }

    var overlay = document.createElement('div');
    overlay.className = 'anim-upload-overlay';
    overlay.hidden = true;
    overlay.setAttribute('aria-hidden', 'true');

    var spinner = document.createElement('span');
    spinner.className = 'anim-spinner';
    overlay.appendChild(spinner);
    dropzone.appendChild(overlay);

    function sync() {
      overlay.hidden = meter.hidden;
    }

    new MutationObserver(sync).observe(meter, {
      attributes: true,
      attributeFilter: ['hidden']
    });

    sync();
  }

  /* ==========================================================================
     14. 动态按钮补装饰 + 图表兜底
     ========================================================================== */

  function initDynamicDecorators() {
    ['pager', 'taskPager'].forEach(function (id) {
      var host = $(id);
      if (!host) {
        return;
      }
      new MutationObserver(function () {
        decorateButtons(host);
      }).observe(host, { childList: true });
    });

    // 若图表库未成功渲染，兜底显示，避免一直停留在透明状态
    setTimeout(function () {
      qsa('.anim-chart').forEach(function (el) {
        if (!el.classList.contains('anim-chart-ready')) {
          addClass(el, 'anim-chart-ready');
        }
      });
    }, 3000);
  }

  /* ==========================================================================
     启动
     ========================================================================== */

  function init() {
    decorateStatic();
    initScrollProgress();
    initReveal();
    initStagger();
    initRipple();
    initMagnetic();
    initTilt();
    initToasts();
    initCompletionWatcher();
    initValidationFeedback();
    initDeleteFeedback();
    initExportBurst();
    initRunState();
    initUploadSpinner();
    initDynamicDecorators();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
