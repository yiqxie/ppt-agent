import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { MsalProvider, useMsal } from "@azure/msal-react";
import type { AccountInfo, PublicClientApplication } from "@azure/msal-browser";
import { acquireToken, createMsalInstance, getApiScope } from "./msal";
import { fetchPublicConfig, setApiTokenProvider } from "../api/client";
import type { PublicConfig } from "../api/types";

interface AuthState {
  ready: boolean;
  config: PublicConfig | null;
  account: AccountInfo | null;
  signIn: () => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthState>({
  ready: false,
  config: null,
  account: null,
  signIn: async () => {},
  signOut: () => {},
});

interface ProviderProps {
  children: ReactNode;
}

/**
 * 顶层 AuthProvider：
 * 1) 拉 /api/config 决定是否启用 MSAL
 * 2) 启用时把 MsalProvider 包到下层，并把 token 注入 axios
 */
export function AppAuthProvider({ children }: ProviderProps) {
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [instance, setInstance] = useState<PublicClientApplication | null>(null);

  useEffect(() => {
    fetchPublicConfig()
      .then(async (cfg) => {
        setConfig(cfg);
        const inst = createMsalInstance(cfg);
        if (inst) {
          await inst.initialize();
          await inst.handleRedirectPromise().catch(() => {});
          setInstance(inst);
        }
      })
      .catch((e) => {
        console.error("拉取配置失败", e);
        setConfig({ app_name: "PPT Slide Agent", auth_enabled: false });
      });
  }, []);

  if (!config) {
    return null;
  }

  if (config.auth_enabled && instance) {
    return (
      <MsalProvider instance={instance}>
        <InnerAuthBridge config={config}>{children}</InnerAuthBridge>
      </MsalProvider>
    );
  }

  // 未启用认证：直接渲染
  return (
    <AuthContext.Provider
      value={{
        ready: true,
        config,
        account: null,
        signIn: async () => {},
        signOut: () => {},
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

function InnerAuthBridge({ config, children }: { config: PublicConfig; children: ReactNode }) {
  const { instance, accounts } = useMsal();
  const account = accounts[0] ?? null;
  const scope = useMemo(() => getApiScope(config), [config]);

  useEffect(() => {
    setApiTokenProvider(async () => {
      if (!account || !scope) return null;
      return await acquireToken(instance as PublicClientApplication, scope, account);
    });
    return () => setApiTokenProvider(null);
  }, [instance, account, scope]);

  const ctxValue = useMemo<AuthState>(
    () => ({
      ready: true,
      config,
      account,
      async signIn() {
        await instance.loginPopup({ scopes: scope ? [scope] : ["User.Read"] });
      },
      signOut() {
        instance.logoutPopup({ account: account ?? undefined });
      },
    }),
    [instance, account, scope, config],
  );

  return <AuthContext.Provider value={ctxValue}>{children}</AuthContext.Provider>;
}

export function useAppAuth(): AuthState {
  return useContext(AuthContext);
}
