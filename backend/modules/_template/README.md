# Custom Provider Module Template

This directory provides a template for creating your own provider modules in **MyAIrouter**.

## 🚀 How to Create a Custom Module

1. **Duplicate this directory**:
   Copy `_template` to a new folder inside `backend/modules/` without the leading underscore, for example:
   ```bash
   cp -r backend/modules/_template backend/modules/my_service
   ```

2. **Configure `manifest.json`**:
   - `id`: unique identifier (slug, e.g. `codex_oauth` or `deepseek_web`).
   - `name`: human-readable title shown in the web console.
   - `description`: what this module does.
   - `fields`: list of credential/input fields needed when creating a profile (tokens, cookies, urls, headers).
   - `default_models`: models exposed to the gateway catalog.

3. **Implement `handler.py`**:
   - Subclass `BaseModuleAdapter`.
   - Implement:
     - `validate_credentials(ctx)`: test connection and credentials health.
     - `list_models(ctx)`: return models available for this profile.
     - `chat_completions(request, ctx)`: handle standard OpenAI-compatible requests.
     - `stream_chat(request, ctx)`: handle SSE streaming chunks.
   - Use `ctx.proxy_url` for making requests through SOCKS5/HTTP proxies configured by the user.
   - Use `self.create_http_client(ctx)` to get a ready-to-use async HTTPX client with proxy support.

4. **Rescan in Web Console**:
   Go to **Modules** in the sidebar and click **Rescan Modules**. Your module will appear immediately!

5. **Create Profiles & Assign Proxies**:
   - Click **Add Profile** on your module card.
   - Fill in your custom fields.
   - Select any proxy from your proxy pool.
   - Test connection live!
