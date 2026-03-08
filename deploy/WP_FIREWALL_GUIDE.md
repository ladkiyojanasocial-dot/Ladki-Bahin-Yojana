# Troubleshooting WordPress API 403 and HTML Block Pages

If the agent sometimes publishes and sometimes fails with `Non-JSON response type: text/html`, the problem is not your article payload. A firewall or bot-protection layer is intermittently challenging requests to `/wp-json/`.

## Option A: Publish via webhook (recommended)

This is the reliable fix. The agent sends the article to a private PHP file in your WordPress root, and that file creates the post locally inside WordPress. That bypasses Cloudflare and Wordfence blocks on the REST API.

1. Copy [kisan-agent-webhook.php](/G:/Kisan%20Portal%20Alerts%20App/deploy/kisan-agent-webhook.php) to your WordPress site root.
2. Rename it to something unguessable, for example `kisan-publish-a1b2c3.php`.
3. In `wp-config.php` add:

```php
define('KISAN_AGENT_WEBHOOK_SECRET', 'your-long-random-secret');
```

4. Optional: choose which WordPress user owns posts published by the webhook:

```php
define('KISAN_AGENT_WEBHOOK_AUTHOR', 'your-login-name');
// or
define('KISAN_AGENT_WEBHOOK_USER_ID', 2);
```

5. In the agent `.env` add:

```env
WP_PUBLISH_WEBHOOK_URL=https://kisanportal.org/kisan-publish-a1b2c3.php
WP_PUBLISH_SECRET=your-long-random-secret
```

6. Test the endpoint in a browser:
   `https://kisanportal.org/kisan-publish-a1b2c3.php`
   It should return a small JSON ping response.

After this, the agent will use the webhook automatically for both draft creation and draft publishing.

## Option B: Keep REST API and relax the firewall

If you prefer not to use the webhook, you still need to allow `/wp-json/` through Wordfence or Cloudflare.

### Wordfence

1. Log in to WordPress.
2. Go to `Wordfence > Firewall`.
3. Add an allowlist rule for `/wp-json/wp/v2/`.
4. If your runner IP is fixed, allowlist that IP too.

### Cloudflare

If you are on the free plan and `Bot Fight Mode` is on, REST requests may be challenged unpredictably. Turn it off for this path, or use the webhook instead.

If you are on a paid plan, add a WAF rule to skip checks when `URI Path` starts with `/wp-json/`.

## Why this started suddenly

This kind of failure often appears without any code change in the agent because the block is upstream:

- Cloudflare bot heuristics changed
- Wordfence started challenging the request pattern
- hosting or CDN security rules changed
- the request hit a challenge page instead of JSON

That is why it can work one run and fail on the next.
