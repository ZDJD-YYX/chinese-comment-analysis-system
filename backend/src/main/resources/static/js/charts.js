/**
 * ECharts 图表配置与渲染。
 *
 * 系统中只保留两张核心图表，它们承担不同的表达任务：
 *   1. 情感分布饼图 —— 回答"三类情感各占多少"，用占比直观呈现结构；
 *   2. 热点词云   —— 回答"大家在说什么"，用字号表达 TF-IDF 权重。
 *
 * 颜色只表示情感语义（正面绿 / 负面红 / 中性灰），不用于装饰。
 */
(function (global) {
  'use strict';

  /** 情感语义色，与 style.css 中的 --pos / --neg / --neu 保持一致 */
  var SENTIMENT_COLOR = {
    POSITIVE: '#2F9E6B',
    NEGATIVE: '#D9534F',
    NEUTRAL: '#9C8F84'
  };

  /** 浅底上更沉稳的扇形渐变，让饼图有体积感 */
  var SENTIMENT_GRADIENT = {
    POSITIVE: { type: 'linear', x: 0, y: 0, x2: 1, y2: 1, colorStops: [
      { offset: 0, color: '#6FC79B' }, { offset: 1, color: '#1F7A50' }
    ] },
    NEGATIVE: { type: 'linear', x: 0, y: 0, x2: 1, y2: 1, colorStops: [
      { offset: 0, color: '#E88C84' }, { offset: 1, color: '#B03A36' }
    ] },
    NEUTRAL: { type: 'linear', x: 0, y: 0, x2: 1, y2: 1, colorStops: [
      { offset: 0, color: '#C3B4A5' }, { offset: 1, color: '#7A6C61' }
    ] }
  };

  var SENTIMENT_LABEL = {
    POSITIVE: '正面',
    NEGATIVE: '负面',
    NEUTRAL: '中性'
  };

  /** 词云"全部"视角下的暖色渐层，用于按权重大小分层着色 */
  var AURORA_RAMP = ['#A94A2B', '#B4532F', '#C4673A', '#D9764A', '#E9A25B'];

  /** 单一情感维度下的明暗渐层 */
  var SENTIMENT_RAMP = {
    POSITIVE: ['#1F7A50', '#2F9E6B', '#4FB383', '#6FC79B', '#A5DCC2'],
    NEGATIVE: ['#A5382F', '#C0483F', '#D9534F', '#E88C84', '#F3B7B1'],
    NEUTRAL: ['#6E6156', '#7A6C61', '#9C8F84', '#B4A79B', '#D5CABF']
  };

  /** 图表点击联动回调：词云选词、饼图选情感 */
  var clickHandlers = { word: null, sentiment: null };

  var TOOLTIP_STYLE = {
    backgroundColor: 'rgba(255, 250, 244, .97)',
    borderColor: '#E8D9C8',
    borderWidth: 1,
    padding: [9, 12],
    textStyle: { color: '#3A2C22', fontSize: 12, fontFamily: '"PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif' },
    extraCssText: 'border-radius:10px;box-shadow:0 18px 40px -16px rgba(74,45,28,.35);'
  };

  var UI_FONT = '"PingFang SC", "Microsoft YaHei", "Hiragino Sans GB", "Segoe UI", sans-serif';
  var NUM_FONT = '"Bahnschrift", "DIN Alternate", "Helvetica Neue", Arial, sans-serif';

  /** 图表实例缓存，避免重复初始化造成内存泄漏 */
  var instances = { pie: null, cloud: null, trend: null };

  /**
   * 懒加载图表实例。
   * @param {string} key 缓存键，'pie' 或 'cloud'
   * @param {HTMLElement} element 容器
   * @returns {object|null} ECharts 实例，图表库未加载时返回 null
   */
  function useChart(key, element) {
    if (typeof echarts === 'undefined' || !element) {
      return null;
    }
    if (!instances[key] || instances[key].isDisposed()) {
      instances[key] = echarts.init(element, null, { renderer: 'canvas' });
    }
    return instances[key];
  }

  /**
   * 在图表容器内取得（必要时创建）环心读数层。
   * 用 HTML 覆盖层而不是 ECharts title，避免 title 在居中时的二次偏移。
   * @param {HTMLElement} element 图表容器
   * @returns {HTMLElement} 读数层
   */
  function ensureCenter(element) {
    var center = element.querySelector('.chart-center');
    if (!center) {
      center = document.createElement('div');
      center.className = 'chart-center';
      center.setAttribute('aria-hidden', 'true');
      center.innerHTML = ''
        + '<span class="chart-center__value"></span>'
        + '<span class="chart-center__label">平均置信度</span>';
      element.appendChild(center);
    }
    return center;
  }

  /**
   * 在图表中央展示空状态文案。
   * @param {object} chart ECharts 实例
   * @param {string} text  提示文案
   */
  function showEmpty(chart, text) {
    chart.clear();

    var element = chart.getDom();
    var center = element.querySelector('.chart-center');
    if (center) {
      center.hidden = true;
    }

    var empty = element.querySelector('.chart-empty');
    if (!empty) {
      empty = document.createElement('div');
      empty.className = 'chart-empty';
      empty.setAttribute('aria-hidden', 'true');
      element.appendChild(empty);
    }
    empty.textContent = text;
    empty.hidden = false;
  }

  /**
   * 图表首次渲染完成后打上标记，交给 Motion.Lab 的淡入动效接管。
   * @param {HTMLElement} element 容器
   */
  function markReady(element) {
    if (element && element.classList) {
      element.classList.add('anim-chart-ready');
    }
  }

  /* ==========================================================================
     情感分布饼图
     ========================================================================== */

  /**
   * 渲染情感分布环形图。
   * @param {HTMLElement} element 容器
   * @param {object} stats 情感统计（SentimentStatisticsVO）
   */
  function renderPie(element, stats) {
    var chart = useChart('pie', element);
    if (!chart) {
      return;
    }

    var total = Number((stats && stats.totalCount) || 0);
    if (!total) {
      showEmpty(chart, '该任务暂无分析结果');
      markReady(element);
      return;
    }

    var raw = [
      { key: 'POSITIVE', name: SENTIMENT_LABEL.POSITIVE, value: Number(stats.positiveCount || 0), color: SENTIMENT_COLOR.POSITIVE },
      { key: 'NEGATIVE', name: SENTIMENT_LABEL.NEGATIVE, value: Number(stats.negativeCount || 0), color: SENTIMENT_COLOR.NEGATIVE },
      { key: 'NEUTRAL', name: SENTIMENT_LABEL.NEUTRAL, value: Number(stats.neutralCount || 0), color: SENTIMENT_COLOR.NEUTRAL }
    ];

    // 预先算好占比，供图例与提示框复用，避免依赖 ECharts 内部百分比
    var data = raw.map(function (item) {
      item.pct = total ? (item.value / total) * 100 : 0;
      return item;
    });

    var avgConfidence = stats.avgConfidence;
    var centerValue = (avgConfidence === null || avgConfidence === undefined || avgConfidence === '')
      ? '—'
      : (Number(avgConfidence) * 100).toFixed(1) + '%';

    chart.clear();
    chart.setOption({
      tooltip: {
        trigger: 'item',
        backgroundColor: TOOLTIP_STYLE.backgroundColor,
        borderColor: TOOLTIP_STYLE.borderColor,
        borderWidth: 1,
        padding: TOOLTIP_STYLE.padding,
        textStyle: TOOLTIP_STYLE.textStyle,
        extraCssText: TOOLTIP_STYLE.extraCssText,
        formatter: function (params) {
          var item = params.data || {};
          return item.name + '：' + item.value + ' 条（' + (item.pct || 0).toFixed(1) + '%）';
        }
      },
      legend: {
        bottom: 0,
        left: 'center',
        icon: 'circle',
        itemWidth: 8,
        itemHeight: 8,
        itemGap: 18,
        textStyle: { fontSize: 12, color: '#5E4B3C', fontFamily: UI_FONT },
        formatter: function (name) {
          var hit = null;
          data.forEach(function (item) {
            if (item.name === name) {
              hit = item;
            }
          });
          return hit ? name + ' ' + hit.pct.toFixed(1) + '%' : name;
        }
      },
      series: [
        {
          type: 'pie',
          radius: ['56%', '76%'],
          center: ['50%', '43%'],
          avoidLabelOverlap: true,
          // 不设 minAngle：条数为 0 的情感维度不应画出扇形（图例仍保留该项，显示 0.0%）
          label: { show: false },
          labelLine: { show: false },
          itemStyle: { borderColor: '#FFFFFF', borderWidth: 3, borderRadius: 4 },
          emphasis: {
            scale: true,
            scaleSize: 6,
            itemStyle: {
              shadowBlur: 24,
              shadowColor: 'rgba(180, 83, 47, .28)',
              borderColor: '#FFFFFF',
              borderWidth: 3
            }
          },
          data: data.map(function (item) {
            return {
              name: item.name,
              value: item.value,
              pct: item.pct,
              key: item.key,
              itemStyle: {
                color: SENTIMENT_GRADIENT[item.key] || item.color
              }
            };
          })
        }
      ]
    }, true);
    markReady(element);

    var empty = element.querySelector('.chart-empty');
    if (empty) {
      empty.hidden = true;
    }
    var center = ensureCenter(element);
    center.hidden = false;
    center.querySelector('.chart-center__value').textContent = centerValue;

    // 点击扇区联动筛选明细表
    chart.off('click');
    chart.on('click', function (params) {
      var item = params && params.data;
      if (item && item.key && typeof clickHandlers.sentiment === 'function') {
        clickHandlers.sentiment(item.key);
      }
    });
  }

  /* ==========================================================================
     热点词云
     ========================================================================== */

  /**
   * 解析词云配色：按当前筛选的情感维度选择色板。
   * @param {string} sentiment ALL / POSITIVE / NEGATIVE / NEUTRAL
   * @returns {string[]} 色板
   */
  function paletteOf(sentiment) {
    if (sentiment === 'POSITIVE' || sentiment === 'NEGATIVE' || sentiment === 'NEUTRAL') {
      return SENTIMENT_RAMP[sentiment];
    }
    return AURORA_RAMP;
  }

  /**
   * 取词条配色。
   * 兼容两种入参：ECharts 包装后的 params（数据在 .data）与原始数据项。
   * @param {object} item 词条
   * @param {string[]} palette 色板
   * @returns {string} 颜色值
   */
  function toneColor(item, palette) {
    var source = (item && item.data && typeof item.data.tone === 'number') ? item.data : item;
    var tone = (source && typeof source.tone === 'number') ? source.tone : 0;
    return palette[tone % palette.length];
  }

  /**
   * 渲染热点词云。
   * @param {HTMLElement} element   容器
   * @param {Array}       keywords  关键词列表（KeywordVO[]）
   * @param {string}      sentiment 当前情感维度
   */
  function renderCloud(element, keywords, sentiment) {
    if (!element) {
      return;
    }
    var list = (keywords || []).filter(function (item) {
      return item && item.word;
    });
    if (!list.length) {
      var emptyChart = useChart('cloud', element);
      if (emptyChart) {
        showEmpty(emptyChart, '该维度暂未提取到关键词');
      }
      markReady(element);
      return;
    }

    // 词云插件未加载时退化为 HTML 标签云，保证信息不丢失
    if (global.__wordCloudFailed) {
      renderCloudFallback(element, list, sentiment);
      return;
    }

    var chart = useChart('cloud', element);
    if (!chart) {
      return;
    }

    var weights = list.map(function (item) {
      return Number(item.weight || 0);
    });
    var maxWeight = Math.max.apply(null, weights);
    var minWeight = Math.min.apply(null, weights);
    var palette = paletteOf(sentiment);

    var data = list.map(function (item, index) {
      var weight = Number(item.weight || 0);
      // 权重归一到 0~1，用于在色板中分层；权重全相同时统一用最深色
      var ratio = maxWeight > minWeight ? (weight - minWeight) / (maxWeight - minWeight) : 1;
      return {
        name: item.word,
        value: weight,
        wordCount: item.wordCount,
        tone: Math.min(palette.length - 1, Math.round(ratio * (palette.length - 1))),
        // 序号仅用于提示框展示，避免同名关键词混淆
        index: index
      };
    });

    chart.clear();
    chart.setOption({
      tooltip: {
        show: true,
        backgroundColor: TOOLTIP_STYLE.backgroundColor,
        borderColor: TOOLTIP_STYLE.borderColor,
        borderWidth: 1,
        padding: TOOLTIP_STYLE.padding,
        textStyle: TOOLTIP_STYLE.textStyle,
        extraCssText: TOOLTIP_STYLE.extraCssText,
        formatter: function (params) {
          var item = params.data || {};
          var count = (item.wordCount === null || item.wordCount === undefined) ? '—' : item.wordCount;
          return item.name + '<br/>TF-IDF 权重：' + Number(item.value).toFixed(4) + '<br/>出现次数：' + count;
        }
      },
      series: [
        {
          type: 'wordCloud',
          left: 'center',
          top: 'center',
          width: '98%',
          height: '94%',
          shape: 'circle',
          // 中文横向排布可读性最好，因此不做旋转
          rotationRange: [0, 0],
          gridSize: 9,
          sizeRange: [13, 46],
          drawOutOfBound: false,
          layoutAnimation: true,
          textStyle: {
            fontFamily: UI_FONT,
            fontWeight: 600,
            color: function (item) {
              return toneColor(item, palette);
            }
          },
          emphasis: {
            textStyle: { textShadowBlur: 16, textShadowColor: 'rgba(180, 83, 47, .45)' }
          },
          data: data
        }
      ]
    }, true);
    markReady(element);

    var empty = element.querySelector('.chart-empty');
    if (empty) {
      empty.hidden = true;
    }

    // 点击词条联动筛选明细表
    chart.off('click');
    chart.on('click', function (params) {
      if (params && params.name && typeof clickHandlers.word === 'function') {
        clickHandlers.word(params.name);
      }
    });
  }

  /**
   * 词云插件不可用时的降级渲染：用字号区分权重，按行流式排布。
   * @param {HTMLElement} element   容器
   * @param {Array}       keywords  关键词列表
   * @param {string}      sentiment 当前情感维度
   */
  function renderCloudFallback(element, keywords, sentiment) {
    var palette = paletteOf(sentiment);
    var weights = keywords.map(function (item) {
      return Number(item.weight || 0);
    });
    var maxWeight = Math.max.apply(null, weights);
    var minWeight = Math.min.apply(null, weights);

    element.innerHTML = '<div class="cloud-fallback"></div>';
    var host = element.firstChild;
    keywords.slice(0, 60).forEach(function (item) {
      var weight = Number(item.weight || 0);
      var ratio = maxWeight > minWeight ? (weight - minWeight) / (maxWeight - minWeight) : 1;
      var span = document.createElement('span');
      span.textContent = item.word;
      span.style.fontSize = (13 + ratio * 22).toFixed(1) + 'px';
      span.style.color = palette[Math.min(palette.length - 1, Math.round(ratio * (palette.length - 1)))];
      span.title = 'TF-IDF 权重：' + weight.toFixed(4);
      host.appendChild(span);
    });
    markReady(element);

    var empty = element.querySelector('.chart-empty');
    if (empty) {
      empty.hidden = true;
    }
  }

  /**
   * 渲染最近 7 天任务量柱状图（数据看板）。
   *
   * <p>只表达"每天创建了多少个任务"，不叠加情感维度，
   * 避免与任务详情页的情感图表混淆。</p>
   *
   * @param {HTMLElement} element 容器
   * @param {Array}       points  每日任务量 [{date, count}]
   */
  function renderTrend(element, points) {
    var chart = useChart('trend', element);
    if (!chart) {
      return;
    }
    var list = (points || []).filter(function (item) {
      return item && item.date;
    });
    if (!list.length) {
      showEmpty(chart, '最近 7 天暂无任务');
      markReady(element);
      return;
    }

    var dates = list.map(function (item) {
      return item.date;
    });
    var values = list.map(function (item) {
      return Number(item.count || 0);
    });

    chart.clear();
    chart.setOption({
      grid: { left: 6, right: 14, top: 18, bottom: 2, containLabel: true },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: TOOLTIP_STYLE.backgroundColor,
        borderColor: TOOLTIP_STYLE.borderColor,
        borderWidth: 1,
        padding: TOOLTIP_STYLE.padding,
        textStyle: TOOLTIP_STYLE.textStyle,
        extraCssText: TOOLTIP_STYLE.extraCssText,
        formatter: function (params) {
          var item = (params && params[0]) || {};
          return item.axisValue + '：' + item.value + ' 个任务';
        }
      },
      xAxis: {
        type: 'category',
        data: dates,
        axisTick: { show: false },
        axisLine: { lineStyle: { color: '#E8D9C8' } },
        axisLabel: { color: '#6A5645', fontSize: 11, fontFamily: UI_FONT }
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        splitLine: { lineStyle: { color: '#F1E6D9' } },
        axisLabel: { color: '#7C6855', fontSize: 11, fontFamily: NUM_FONT }
      },
      series: [
        {
          type: 'bar',
          data: values,
          barWidth: '46%',
          itemStyle: {
            borderRadius: [6, 6, 2, 2],
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: '#C4673A' },
                { offset: 1, color: '#A94A2B' }
              ]
            }
          },
          emphasis: { itemStyle: { color: '#963E21' } },
          label: {
            show: true,
            position: 'top',
            color: '#7C6855',
            fontSize: 11,
            fontFamily: NUM_FONT
          }
        }
      ]
    }, true);
    markReady(element);

    var empty = element.querySelector('.chart-empty');
    if (empty) {
      empty.hidden = true;
    }
  }

  /**
   * 渲染任务级情感趋势折线图（FR-BIZ-18）。
   *
   * @param {HTMLElement} element     容器
   * @param {Array} points            时间桶数据：[{bucket, positive, negative, neutral}]
   * @param {string} granularity      聚合粒度：hour / day
   */
  function renderSentimentTrend(element, points, granularity) {
    var chart = useChart('taskTrend', element);
    if (!chart) {
      return;
    }
    var list = (points || []).filter(function (item) {
      return item && item.bucket;
    });
    if (!list.length) {
      showEmpty(chart, '该任务没有可用的评论时间，无法生成趋势');
      markReady(element);
      return;
    }

    var hourly = granularity === 'hour';
    // 轴标签只保留必要部分：按天显示 MM-dd，按小时显示 HH:00
    var labels = list.map(function (item) {
      var bucket = String(item.bucket);
      if (hourly) {
        return bucket.length >= 16 ? bucket.slice(11, 16) : bucket;
      }
      return bucket.length >= 10 ? bucket.slice(5, 10) : bucket;
    });

    var series = [
      { name: '正面', key: 'positive', color: SENTIMENT_COLOR.POSITIVE },
      { name: '负面', key: 'negative', color: SENTIMENT_COLOR.NEGATIVE },
      { name: '中性', key: 'neutral', color: SENTIMENT_COLOR.NEUTRAL }
    ].map(function (item) {
      return {
        name: item.name,
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        showSymbol: list.length <= 24,
        lineStyle: { width: 2, color: item.color },
        itemStyle: { color: item.color },
        areaStyle: { opacity: .08, color: item.color },
        data: list.map(function (point) {
          return Number(point[item.key] || 0);
        })
      };
    });

    chart.clear();
    chart.setOption({
      color: [SENTIMENT_COLOR.POSITIVE, SENTIMENT_COLOR.NEGATIVE, SENTIMENT_COLOR.NEUTRAL],
      legend: {
        top: 0,
        right: 4,
        itemWidth: 10,
        itemHeight: 10,
        textStyle: { color: '#6A5645', fontSize: 11, fontFamily: UI_FONT }
      },
      grid: { left: 6, right: 16, top: 34, bottom: 2, containLabel: true },
      tooltip: {
        trigger: 'axis',
        backgroundColor: TOOLTIP_STYLE.backgroundColor,
        borderColor: TOOLTIP_STYLE.borderColor,
        borderWidth: 1,
        padding: TOOLTIP_STYLE.padding,
        textStyle: TOOLTIP_STYLE.textStyle,
        extraCssText: TOOLTIP_STYLE.extraCssText,
        formatter: function (params) {
          var rows = params || [];
          if (!rows.length) {
            return '';
          }
          var original = list[rows[0].dataIndex];
          var lines = [original.bucket];
          rows.forEach(function (row) {
            lines.push(row.marker + row.seriesName + '：' + row.value + ' 条');
          });
          return lines.join('<br>');
        }
      },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: labels,
        axisTick: { show: false },
        axisLine: { lineStyle: { color: '#E8D9C8' } },
        axisLabel: { color: '#6A5645', fontSize: 11, fontFamily: NUM_FONT }
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        splitLine: { lineStyle: { color: '#F1E6D9' } },
        axisLabel: { color: '#7C6855', fontSize: 11, fontFamily: NUM_FONT }
      },
      series: series
    }, true);
    markReady(element);

    var empty = element.querySelector('.chart-empty');
    if (empty) {
      empty.hidden = true;
    }
  }

  /**
   * 渲染置信度分布直方图。
   *
   * 低于复核阈值的区间用负面色标出，超过阈值的用品牌色，一眼看出低置信度规模。
   * @param {HTMLElement} element 容器
   * @param {object} data ConfidenceDistributionVO
   */
  function renderConfidence(element, data) {
    var chart = useChart('confidence', element);
    if (!chart) {
      return;
    }
    var buckets = (data && data.buckets) || [];
    var total = Number((data && data.totalCount) || 0);
    if (!buckets.length || !total) {
      showEmpty(chart, '该任务暂无可统计的置信度数据');
      markReady(element);
      return;
    }
    var threshold = Number((data && data.threshold) || 0.6);

    chart.clear();
    chart.setOption({
      grid: { left: 6, right: 12, top: 22, bottom: 4, containLabel: true },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: TOOLTIP_STYLE.backgroundColor,
        borderColor: TOOLTIP_STYLE.borderColor,
        borderWidth: 1,
        padding: TOOLTIP_STYLE.padding,
        textStyle: TOOLTIP_STYLE.textStyle,
        extraCssText: TOOLTIP_STYLE.extraCssText,
        formatter: function (params) {
          var item = (params && params[0]) || {};
          var bucket = buckets[item.dataIndex] || {};
          var pct = Number(bucket.ratio || 0) * 100;
          return bucket.label + '<br/>' + item.value + ' 条（' + pct.toFixed(1) + '%）';
        }
      },
      xAxis: {
        type: 'category',
        data: buckets.map(function (item) {
          return item.label;
        }),
        axisTick: { show: false },
        axisLine: { lineStyle: { color: '#E8D9C8' } },
        axisLabel: {
          color: '#6A5645',
          fontSize: 10,
          interval: 0,
          rotate: 32,
          fontFamily: NUM_FONT
        }
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        splitLine: { lineStyle: { color: '#F1E6D9' } },
        axisLabel: { color: '#7C6855', fontSize: 11, fontFamily: NUM_FONT }
      },
      series: [
        {
          type: 'bar',
          barWidth: '58%',
          data: buckets.map(function (item) {
            // 区间上限不超过阈值即视为低置信度区间
            var low = Number(item.upper || 0) <= threshold + 1e-9;
            return {
              value: Number(item.count || 0),
              itemStyle: {
                borderRadius: [4, 4, 0, 0],
                color: low ? 'rgba(217, 83, 79, .78)' : 'rgba(180, 83, 47, .82)'
              }
            };
          }),
          markLine: {
            silent: true,
            symbol: 'none',
            label: {
              formatter: '复核阈值',
              color: '#7C6855',
              fontSize: 10,
              position: 'insideEndTop'
            },
            lineStyle: { color: '#D9534F', type: 'dashed', width: 1 },
            data: [{ xAxis: Math.max(0, Math.min(9, Math.round(threshold * 10) - 1)) }]
          }
        }
      ]
    }, true);
    markReady(element);

    var empty = element.querySelector('.chart-empty');
    if (empty) {
      empty.hidden = true;
    }
  }

  /**
   * 渲染负面评论关键词 Top 横向条形图。
   * @param {HTMLElement} element 容器
   * @param {Array} keywords KeywordVO[]
   */
  function renderNegativeTop(element, keywords) {
    var chart = useChart('negative', element);
    if (!chart) {
      return;
    }
    var list = (keywords || []).filter(function (item) {
      return item && item.word;
    }).slice(0, 10);
    if (!list.length) {
      showEmpty(chart, '该任务没有负面评论关键词');
      markReady(element);
      return;
    }
    // 横向条形的类目轴自下而上绘制，反转后权重最高的词显示在顶部
    var reversed = list.slice().reverse();

    chart.clear();
    chart.setOption({
      grid: { left: 4, right: 42, top: 8, bottom: 4, containLabel: true },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: TOOLTIP_STYLE.backgroundColor,
        borderColor: TOOLTIP_STYLE.borderColor,
        borderWidth: 1,
        padding: TOOLTIP_STYLE.padding,
        textStyle: TOOLTIP_STYLE.textStyle,
        extraCssText: TOOLTIP_STYLE.extraCssText,
        formatter: function (params) {
          var item = (params && params[0]) || {};
          var data = item.data || {};
          return item.name + '<br/>TF-IDF 权重：' + Number(data.weight || 0).toFixed(4)
            + '<br/>出现次数：' + (data.wordCount === undefined || data.wordCount === null
              ? '—' : data.wordCount);
        }
      },
      xAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: '#F1E6D9' } },
        axisLabel: { color: '#7C6855', fontSize: 10, fontFamily: NUM_FONT }
      },
      yAxis: {
        type: 'category',
        data: reversed.map(function (item) {
          return item.word;
        }),
        axisTick: { show: false },
        axisLine: { lineStyle: { color: '#E8D9C8' } },
        axisLabel: { color: '#554334', fontSize: 11.5, fontFamily: UI_FONT }
      },
      series: [
        {
          type: 'bar',
          barWidth: '56%',
          data: reversed.map(function (item) {
            return {
              value: Number(item.weight || 0),
              weight: Number(item.weight || 0),
              wordCount: item.wordCount
            };
          }),
          itemStyle: {
            borderRadius: [0, 5, 5, 0],
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 1,
              y2: 0,
              colorStops: [
                { offset: 0, color: 'rgba(217, 83, 79, .55)' },
                { offset: 1, color: 'rgba(165, 56, 47, .92)' }
              ]
            }
          },
          label: {
            show: true,
            position: 'right',
            color: '#7C6855',
            fontSize: 10,
            fontFamily: NUM_FONT,
            formatter: function (params) {
              return Number(params.value || 0).toFixed(3);
            }
          }
        }
      ]
    }, true);
    markReady(element);

    var empty = element.querySelector('.chart-empty');
    if (empty) {
      empty.hidden = true;
    }
  }

  /**
   * 渲染任务对比用的分组条形图（两任务同一指标并排）。
   *
   * @param {string}      key        图表实例键
   * @param {HTMLElement} element    容器
   * @param {string[]}    categories 类目
   * @param {number[]}    seriesA    A 任务数值（百分比）
   * @param {number[]}    seriesB    B 任务数值（百分比）
   * @param {string}      nameA      A 任务名
   * @param {string}      nameB      B 任务名
   * @param {string}      emptyText  无数据提示
   */
  function renderCompareGrouped(key, element, categories, seriesA, seriesB,
                                nameA, nameB, emptyText) {
    var chart = useChart(key, element);
    if (!chart) {
      return;
    }
    var hasValue = (seriesA || []).concat(seriesB || []).some(function (value) {
      return Number(value || 0) > 0;
    });
    if (!categories || !categories.length || !hasValue) {
      showEmpty(chart, emptyText);
      markReady(element);
      return;
    }

    var bars = [
      { name: nameA, data: seriesA, color: '#A64A2B' },
      { name: nameB, data: seriesB, color: '#2F6B8F' }
    ].map(function (item) {
      return {
        name: item.name,
        type: 'bar',
        barMaxWidth: 26,
        barGap: '18%',
        data: item.data,
        itemStyle: { borderRadius: [4, 4, 0, 0], color: item.color }
      };
    });

    chart.clear();
    chart.setOption({
      legend: {
        top: 0,
        right: 4,
        itemWidth: 10,
        itemHeight: 10,
        textStyle: { color: '#6A5645', fontSize: 11, fontFamily: UI_FONT }
      },
      grid: { left: 6, right: 14, top: 34, bottom: 4, containLabel: true },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: TOOLTIP_STYLE.backgroundColor,
        borderColor: TOOLTIP_STYLE.borderColor,
        borderWidth: 1,
        padding: TOOLTIP_STYLE.padding,
        textStyle: TOOLTIP_STYLE.textStyle,
        extraCssText: TOOLTIP_STYLE.extraCssText,
        formatter: function (params) {
          var rows = params || [];
          if (!rows.length) {
            return '';
          }
          var lines = [rows[0].axisValue];
          rows.forEach(function (row) {
            lines.push(row.marker + row.seriesName + '：'
              + Number(row.value || 0).toFixed(1) + '%');
          });
          return lines.join('<br>');
        }
      },
      xAxis: {
        type: 'category',
        data: categories,
        axisTick: { show: false },
        axisLine: { lineStyle: { color: '#E8D9C8' } },
        axisLabel: {
          color: '#6A5645',
          fontSize: 10.5,
          interval: 0,
          rotate: categories.length > 5 ? 30 : 0,
          fontFamily: NUM_FONT
        }
      },
      yAxis: {
        type: 'value',
        max: 100,
        splitLine: { lineStyle: { color: '#F1E6D9' } },
        axisLabel: {
          color: '#7C6855',
          fontSize: 11,
          fontFamily: NUM_FONT,
          formatter: '{value}%'
        }
      },
      series: bars
    }, true);
    markReady(element);

    var empty = element.querySelector('.chart-empty');
    if (empty) {
      empty.hidden = true;
    }
  }

  /**
   * 渲染两个任务的情感分布对比。
   *
   * @param {HTMLElement} element 容器
   * @param {object} left  A 任务统计
   * @param {object} right B 任务统计
   * @param {string} nameA A 任务名
   * @param {string} nameB B 任务名
   */
  function renderCompareSentiment(element, left, right, nameA, nameB) {
    var pct = function (stats, key) {
      var total = Number((stats && stats.totalCount) || 0);
      if (!total) {
        return 0;
      }
      return (Number((stats && stats[key]) || 0) / total) * 100;
    };
    renderCompareGrouped('compareSentiment', element,
      [SENTIMENT_LABEL.POSITIVE, SENTIMENT_LABEL.NEGATIVE, SENTIMENT_LABEL.NEUTRAL],
      [pct(left, 'positiveCount'), pct(left, 'negativeCount'), pct(left, 'neutralCount')],
      [pct(right, 'positiveCount'), pct(right, 'negativeCount'), pct(right, 'neutralCount')],
      nameA, nameB, '两个任务都还没有可对比的情感数据');
  }

  /**
   * 渲染两个任务的置信度分布对比。
   *
   * @param {HTMLElement} element 容器
   * @param {object} left  A 任务置信度分布
   * @param {object} right B 任务置信度分布
   * @param {string} nameA A 任务名
   * @param {string} nameB B 任务名
   */
  function renderCompareConfidence(element, left, right, nameA, nameB) {
    var leftBuckets = (left && left.buckets) || [];
    var rightBuckets = (right && right.buckets) || [];
    var base = leftBuckets.length ? leftBuckets : rightBuckets;
    if (!base.length) {
      renderCompareGrouped('compareConfidence', element, [], [], [], nameA, nameB,
        '暂无置信度数据');
      return;
    }
    var ratioOf = function (buckets, index) {
      var bucket = buckets[index];
      return bucket ? Number(bucket.ratio || 0) * 100 : 0;
    };
    renderCompareGrouped('compareConfidence', element,
      base.map(function (item) {
        return item.label;
      }),
      base.map(function (item, index) {
        return ratioOf(leftBuckets, index);
      }),
      base.map(function (item, index) {
        return ratioOf(rightBuckets, index);
      }),
      nameA, nameB, '暂无置信度数据');
  }

  /**
   * 自适应容器尺寸。
   */
  function resize() {
    Object.keys(instances).forEach(function (key) {
      var chart = instances[key];
      if (chart && !chart.isDisposed()) {
        chart.resize();
      }
    });
  }

  global.charts = {
    SENTIMENT_LABEL: SENTIMENT_LABEL,
    renderPie: renderPie,
    renderCloud: renderCloud,
    renderTrend: renderTrend,
    renderSentimentTrend: renderSentimentTrend,
    renderConfidence: renderConfidence,
    renderNegativeTop: renderNegativeTop,
    renderCompareSentiment: renderCompareSentiment,
    renderCompareConfidence: renderCompareConfidence,
    resize: resize,
    /** 注册词云点击回调 */
    onWordClick: function (fn) {
      clickHandlers.word = fn;
    },
    /** 注册饼图扇区点击回调 */
    onPieClick: function (fn) {
      clickHandlers.sentiment = fn;
    }
  };
})(window);
