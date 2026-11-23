/**
 * 接口请求封装。
 *
 * 后端所有 REST 接口统一返回三段式结构 { code, message, data }：
 *   code = 0    业务成功，data 为业务数据
 *   code != 0   业务失败，message 为可直接展示的中文提示
 *
 * 本模块把这层结构收敛到一处：调用方只拿到 data，失败时统一抛出 ApiError，
 * 由 UI 层决定用轻提示还是页面级提示呈现。
 */
(function (global) {
  'use strict';

  /**
   * 接口根地址。
   * 前端页面由 Spring Boot 作为静态资源托管时与接口同源，直接使用相对路径；
   * 若用 file:// 直接打开页面，则回退到本地后端地址（需后端允许跨域）。
   */
  var API_BASE = location.protocol === 'file:' ? 'http://localhost:8080' : '';

  /** 业务成功码 */
  var CODE_SUCCESS = 0;

  /** 未登录或会话过期，用于触发重新登录 */
  var CODE_UNAUTHORIZED = 401;
  var CODE_SESSION_EXPIRED = 1002;

  /**
   * 业务/网络异常。
   * @param {number} code    后端业务码，网络层异常时为 -1
   * @param {string} message 可展示的中文提示
   */
  function ApiError(code, message) {
    this.name = 'ApiError';
    this.code = code;
    this.message = message || '请求失败，请稍后重试';
  }
  ApiError.prototype = Object.create(Error.prototype);
  ApiError.prototype.constructor = ApiError;

  /**
   * 拼装请求地址，跳过空值参数。
   * @param {string} path   接口路径，如 /api/task/list
   * @param {object} params 查询参数
   * @returns {string} 完整地址
   */
  function buildUrl(path, params) {
    var url = API_BASE + path;
    if (!params) {
      return url;
    }
    var parts = [];
    Object.keys(params).forEach(function (key) {
      var value = params[key];
      if (value === undefined || value === null || value === '') {
        return;
      }
      parts.push(encodeURIComponent(key) + '=' + encodeURIComponent(value));
    });
    if (!parts.length) {
      return url;
    }
    return url + (url.indexOf('?') >= 0 ? '&' : '?') + parts.join('&');
  }

  /**
   * 拆解统一响应结构，成功返回 data，失败抛出 ApiError。
   * @param {object} payload 响应体
   * @returns {*} 业务数据
   */
  function unwrap(payload) {
    if (!payload || typeof payload !== 'object' || typeof payload.code === 'undefined') {
      throw new ApiError(-1, '服务返回格式异常');
    }
    if (payload.code !== CODE_SUCCESS) {
      throw new ApiError(payload.code, payload.message);
    }
    return payload.data;
  }

  /**
   * 发送 JSON 请求。
   * @param {string} method  HTTP 方法
   * @param {string} path    接口路径
   * @param {object} options { params, body }
   * @returns {Promise<*>} 业务数据
   */
  async function request(method, path, options) {
    var opts = options || {};
    var init = { method: method, headers: {} };
    if (opts.body !== undefined) {
      init.headers['Content-Type'] = 'application/json;charset=UTF-8';
      init.body = JSON.stringify(opts.body);
    }

    var response;
    try {
      response = await fetch(buildUrl(path, opts.params), init);
    } catch (e) {
      throw new ApiError(-1, '无法连接后端服务，请确认服务已启动');
    }

    var payload;
    try {
      payload = await response.json();
    } catch (e) {
      throw new ApiError(response.status, '服务返回内容无法解析（HTTP ' + response.status + '）');
    }
    return unwrap(payload);
  }

  /**
   * 上传文件（multipart/form-data）。
   * 使用 XMLHttpRequest 以便获取上传阶段的真实进度。
   * @param {string}   path       接口路径
   * @param {File}     file       待上传文件
   * @param {Function} onProgress 上传进度回调，参数为 0~100 的整数
   * @returns {Promise<*>} 业务数据
   */
  function upload(path, file, onProgress) {
    return new Promise(function (resolve, reject) {
      var form = new FormData();
      form.append('file', file);

      var xhr = new XMLHttpRequest();
      xhr.open('POST', API_BASE + path, true);
      xhr.upload.onprogress = function (event) {
        if (event.lengthComputable && typeof onProgress === 'function') {
          onProgress(Math.round((event.loaded / event.total) * 100));
        }
      };
      xhr.onload = function () {
        var payload = null;
        try {
          payload = JSON.parse(xhr.responseText);
        } catch (e) {
          // 交由下方统一报错
        }
        if (!payload) {
          reject(new ApiError(xhr.status, '服务返回内容无法解析（HTTP ' + xhr.status + '）'));
          return;
        }
        try {
          resolve(unwrap(payload));
        } catch (err) {
          reject(err);
        }
      };
      xhr.onerror = function () {
        reject(new ApiError(-1, '上传失败，请检查网络连接'));
      };
      xhr.send(form);
    });
  }

  /**
   * 从 Content-Disposition 中解析文件名。
   * 后端使用 filename*=utf-8''<URL 编码> 的形式，兼容普通 filename 写法。
   * @param {string} header 响应头
   * @returns {string} 文件名，解析失败返回空串
   */
  function parseFilename(header) {
    if (!header) {
      return '';
    }
    var encoded = /filename\*=utf-8''([^;]+)/i.exec(header);
    if (encoded) {
      try {
        return decodeURIComponent(encoded[1]);
      } catch (e) {
        return encoded[1];
      }
    }
    var plain = /filename="?([^";]+)"?/i.exec(header);
    return plain ? plain[1] : '';
  }

  /**
   * 下载文件（用于导出 Excel）。
   * 导出成功时响应为 xlsx 字节流；校验失败时后端仍返回统一 JSON 结构，
   * 因此需先判断响应类型，避免把错误信息写成文件。
   * @param {string} path         接口路径
   * @param {object} params       查询参数
   * @param {string} fallbackName 无法从响应头取到文件名时的兜底名称
   * @returns {Promise<string>} 实际保存的文件名
   */
  async function download(path, params, fallbackName) {
    var response;
    try {
      response = await fetch(buildUrl(path, params));
    } catch (e) {
      throw new ApiError(-1, '无法连接后端服务，请确认服务已启动');
    }

    var contentType = response.headers.get('Content-Type') || '';
    if (contentType.indexOf('application/json') >= 0) {
      var payload = await response.json();
      unwrap(payload);
      throw new ApiError(-1, '导出失败，请稍后重试');
    }
    if (!response.ok) {
      throw new ApiError(response.status, '导出失败（HTTP ' + response.status + '）');
    }

    var blob = await response.blob();
    var filename = parseFilename(response.headers.get('Content-Disposition')) || fallbackName;
    var objectUrl = URL.createObjectURL(blob);
    var link = document.createElement('a');
    link.href = objectUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () {
      URL.revokeObjectURL(objectUrl);
    }, 1000);
    return filename;
  }

  /**
   * 判断是否为登录态失效类错误。
   * @param {Error} error 异常对象
   * @returns {boolean} 是否需重新登录
   */
  function isUnauthorized(error) {
    return !!error && (error.code === CODE_UNAUTHORIZED || error.code === CODE_SESSION_EXPIRED);
  }

  global.api = {
    ApiError: ApiError,
    baseUrl: API_BASE,
    isUnauthorized: isUnauthorized,
    get: function (path, params) {
      return request('GET', path, { params: params });
    },
    post: function (path, body, params) {
      return request('POST', path, { body: body, params: params });
    },
    del: function (path) {
      return request('DELETE', path, null);
    },
    upload: upload,
    download: download
  };
})(window);
