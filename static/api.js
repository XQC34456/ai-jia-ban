// 唯一发请求的地方：返回原始 JSON，解析统一错误契约 {detail}，零财富计算。
// 前端所有组件/Store 都通过 api() 访问后端，绝不直接 fetch。

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

export async function api(path, { method = 'GET', body = null, token = null } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = 'Bearer ' + token;

  const res = await fetch(path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : null,
  });

  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = null; }

  if (!res.ok) {
    // 统一错误契约：业务错误一律 {detail: "..."}
    const msg = (data && data.detail) ? data.detail : `请求失败 (${res.status})`;
    throw new ApiError(res.status, msg);
  }
  return data;
}
