import {
  PublicClientApplication,
  type AccountInfo,
  type Configuration,
} from "@azure/msal-browser";
import type { PublicConfig } from "../api/types";

/**
 * 根据后端 /api/config 动态构造 MSAL 实例。
 * 这样部署时只在后端配置一次 tenant/audience，前端零配置即可。
 */
export function createMsalInstance(config: PublicConfig): PublicClientApplication | null {
  if (!config.auth_enabled) return null;

  const tenantId = config.tenant_id || import.meta.env.VITE_AAD_TENANT_ID || "";
  const clientId = import.meta.env.VITE_AAD_CLIENT_ID || "";
  if (!tenantId || !clientId) {
    console.warn("启用了认证但缺少 tenantId / clientId，跳过 MSAL 初始化");
    return null;
  }

  const msalConfig: Configuration = {
    auth: {
      clientId,
      authority: `https://login.microsoftonline.com/${tenantId}`,
      redirectUri: window.location.origin,
      postLogoutRedirectUri: window.location.origin,
    },
    cache: {
      cacheLocation: "sessionStorage",
      storeAuthStateInCookie: false,
    },
  };

  const instance = new PublicClientApplication(msalConfig);
  return instance;
}

export function getApiScope(config: PublicConfig): string {
  // 后端给的 audience 通常是 api://<app-id>，要的是 api://<app-id>/access_as_user
  const fromEnv = import.meta.env.VITE_AAD_API_SCOPE as string | undefined;
  if (fromEnv) return fromEnv;
  if (config.api_audience && config.api_scope) {
    return `${config.api_audience.replace(/\/$/, "")}/${config.api_scope}`;
  }
  return "";
}

export async function acquireToken(
  instance: PublicClientApplication,
  scope: string,
  account: AccountInfo,
): Promise<string | null> {
  try {
    const result = await instance.acquireTokenSilent({
      account,
      scopes: [scope],
    });
    return result.accessToken;
  } catch {
    try {
      const result = await instance.acquireTokenPopup({ scopes: [scope] });
      return result.accessToken;
    } catch (e) {
      console.error("获取 token 失败", e);
      return null;
    }
  }
}
