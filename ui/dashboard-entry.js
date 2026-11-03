const originalSDK = window.__HERMES_PLUGIN_SDK__;
const search = window.location?.search || "";
const mobile = /(?:^|[?&])hermesMobile=1(?:&|$)/.test(search);
const params = mobile ? new URLSearchParams(search) : null;
let SDK = originalSDK;
if (mobile && originalSDK) {
  const session = params.get("mobileSession") || "";
  const profile = params.get("mobileProfile") || "";
  if (!session || !profile) throw new Error("Reopen voice from the existing Hermes chat.");
  const headers = { "x-talk-mobile": "1", "x-talk-mobile-session": encodeURIComponent(session),
    "x-talk-mobile-profile": encodeURIComponent(profile) };
  SDK = Object.assign({}, originalSDK, {
    desktopOwner: { connectionId: "android", storedSessionId: session, sessionId: session, profile },
    fetchJSON(path, init, timeout) {
      const options = Object.assign({}, init || {});
      options.headers = Object.assign({}, options.headers || {}, headers);
      return originalSDK.fetchJSON(path, options, timeout);
    },
    async validateVoiceMode(status) {
      if (!status || status.voiceMode !== "live" || status.liveAuth !== "subscription" ||
          status.source && status.source !== "codex-app-server" ||
          status.authSource && status.authSource !== "codex-app-server") {
        throw new Error("This chat requires GPT-Live through the ChatGPT subscription.");
      }
      const ready = await SDK.fetchJSON("/api/plugins/hermes-talk/mobile/status");
      if (ready?.contract !== 1 || ready.auth !== "subscription" || !ready.existingChatOnly) {
        throw new Error("The server does not support existing-chat subscription voice.");
      }
      return true;
    },
  });
}
if (SDK && window.__HERMES_PLUGINS__) {
  const surface = createTalkSurface(SDK);
  if (window.__HERMES_TALK_TEST_HOOK__) window.__HERMES_TALK_TEST__ = surface;
  window.__HERMES_PLUGINS__.register("hermes-talk", surface.TalkPage);
}
