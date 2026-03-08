<?php
/**
 * Kisan Portal Agent - Publish webhook (foolproof; no firewall blocking).
 *
 * The agent sends the article JSON to this URL instead of calling the REST API.
 * This script runs on your server, so WordPress is accessed locally.
 *
 * Setup:
 * 1. Copy this file to your WordPress site root (same folder as wp-config.php).
 * 2. Rename it to something unguessable, e.g. kisan-publish-a1b2c3.php.
 * 3. In wp-config.php add: define('KISAN_AGENT_WEBHOOK_SECRET', 'your-long-random-secret');
 * 4. Optional author override:
 *    define('KISAN_AGENT_WEBHOOK_AUTHOR', 'your-wp-login');
 *    or define('KISAN_AGENT_WEBHOOK_USER_ID', 2);
 * 5. In the agent .env set:
 *    WP_PUBLISH_WEBHOOK_URL=https://yoursite.com/kisan-publish-a1b2c3.php
 *    WP_PUBLISH_SECRET=the-same-secret
 *
 * Security: only requests with the correct X-Kisan-Agent-Token are accepted.
 */

header('Content-Type: application/json');

if (!empty($_SERVER['REQUEST_METHOD']) && $_SERVER['REQUEST_METHOD'] === 'GET') {
    http_response_code(200);
    echo json_encode(['ok' => true, 'message' => 'Kisan webhook endpoint']);
    exit;
}

$raw = file_get_contents('php://input');
$data = json_decode($raw, true);
if (!is_array($data)) {
    http_response_code(400);
    echo json_encode(['success' => false, 'message' => 'Invalid JSON']);
    exit;
}

$wp_load = __DIR__ . '/wp-load.php';
if (!is_file($wp_load)) {
    $wp_load = dirname(__DIR__) . '/wp-load.php';
}
if (!is_file($wp_load)) {
    http_response_code(500);
    echo json_encode(['success' => false, 'message' => 'WordPress not found']);
    exit;
}
require_once $wp_load;

$webhook_author_id = 1;
if (defined('KISAN_AGENT_WEBHOOK_USER_ID')) {
    $webhook_author_id = (int) KISAN_AGENT_WEBHOOK_USER_ID;
} elseif (defined('KISAN_AGENT_WEBHOOK_AUTHOR')) {
    $u = get_user_by('login', KISAN_AGENT_WEBHOOK_AUTHOR);
    if ($u) {
        $webhook_author_id = (int) $u->ID;
    }
}

$secret = isset($_SERVER['HTTP_X_KISAN_AGENT_TOKEN']) ? $_SERVER['HTTP_X_KISAN_AGENT_TOKEN'] : '';
$expected = defined('KISAN_AGENT_WEBHOOK_SECRET') ? KISAN_AGENT_WEBHOOK_SECRET : '';
if ($expected === '' || $secret !== $expected) {
    http_response_code(403);
    echo json_encode(['success' => false, 'message' => 'Invalid or missing token']);
    exit;
}

if (!empty($data['action']) && $data['action'] === 'publish_draft' && isset($data['post_id'])) {
    $post_id = (int) $data['post_id'];
    $new_status = isset($data['status']) && in_array($data['status'], ['draft', 'pending', 'publish'], true) ? $data['status'] : 'publish';
    if ($post_id > 0) {
        wp_set_current_user($webhook_author_id);
        $updated = wp_update_post(['ID' => $post_id, 'post_status' => $new_status], true);
        if (!is_wp_error($updated) && $updated > 0) {
            echo json_encode(['success' => true, 'post_id' => $post_id, 'post_url' => get_permalink($post_id), 'status' => $new_status]);
            exit;
        }
        $err_msg = is_wp_error($updated) ? $updated->get_error_message() : 'Update returned 0';
        http_response_code(400);
        echo json_encode(['success' => false, 'message' => $err_msg]);
        exit;
    }
    http_response_code(400);
    echo json_encode(['success' => false, 'message' => 'Invalid post_id']);
    exit;
}

$title = isset($data['title']) ? sanitize_text_field($data['title']) : 'Untitled';
$content = isset($data['content']) ? $data['content'] : '';
$excerpt = isset($data['excerpt']) ? sanitize_textarea_field($data['excerpt']) : '';
$slug = isset($data['slug']) ? sanitize_title($data['slug']) : '';
$status = isset($data['status']) && in_array($data['status'], ['draft', 'pending', 'publish'], true) ? $data['status'] : 'draft';
$tags = isset($data['tags']) && is_array($data['tags']) ? $data['tags'] : [];
$category = isset($data['category']) ? sanitize_text_field($data['category']) : 'Uncategorized';
$rank_title = isset($data['rank_math_title']) ? sanitize_text_field($data['rank_math_title']) : $title;
$rank_desc = isset($data['rank_math_description']) ? sanitize_textarea_field($data['rank_math_description']) : $excerpt;
$rank_kw = isset($data['rank_math_focus_keyword']) ? sanitize_text_field($data['rank_math_focus_keyword']) : '';
$faq_schema = isset($data['faq_schema']) ? $data['faq_schema'] : '';
$lang = isset($data['lang']) ? sanitize_key($data['lang']) : '';

$cat_id = 0;
$terms = get_terms(['taxonomy' => 'category', 'name' => $category, 'hide_empty' => false]);
if (!empty($terms)) {
    $cat_id = (int) $terms[0]->term_id;
} else {
    $created = wp_insert_term($category, 'category');
    if (!is_wp_error($created)) {
        $cat_id = (int) $created['term_id'];
    }
}

$tag_ids = [];
foreach ($tags as $tag_name) {
    $tag_name = sanitize_text_field($tag_name);
    if ($tag_name === '') {
        continue;
    }
    $tag = get_term_by('name', $tag_name, 'post_tag');
    if ($tag) {
        $tag_ids[] = (int) $tag->term_id;
    } else {
        $created = wp_insert_term($tag_name, 'post_tag');
        if (!is_wp_error($created)) {
            $tag_ids[] = (int) $created['term_id'];
        }
    }
}

$featured_id = 0;
if (!empty($data['featured_image_base64']) && !empty($data['featured_image_filename'])) {
    $filename = sanitize_file_name(basename($data['featured_image_filename']));
    $bytes = base64_decode($data['featured_image_base64'], true);
    if ($bytes !== false && strlen($bytes) > 0) {
        $upload = wp_upload_bits($filename, null, $bytes);
        if (empty($upload['error']) && !empty($upload['file'])) {
            $file_path = $upload['file'];
            $attachment = [
                'post_mime_type' => $upload['type'],
                'post_title' => $title,
                'post_content' => '',
                'post_status' => 'inherit',
            ];
            $attach_id = wp_insert_attachment($attachment, $file_path);
            if (!is_wp_error($attach_id)) {
                require_once ABSPATH . 'wp-admin/includes/image.php';
                wp_update_attachment_metadata($attach_id, wp_generate_attachment_metadata($attach_id, $file_path));
                $featured_id = (int) $attach_id;
                $alt_text = isset($data['featured_image_alt']) ? sanitize_text_field($data['featured_image_alt']) : $title;
                update_post_meta($featured_id, '_wp_attachment_image_alt', $alt_text);
            }
        }
    }
}

$post_arr = [
    'post_title' => $title,
    'post_content' => $content,
    'post_excerpt' => $excerpt,
    'post_name' => $slug,
    'post_status' => $status,
    'post_type' => 'post',
    'post_author' => $webhook_author_id,
    'comment_status' => 'open',
];
$post_id = wp_insert_post($post_arr, true);
if (is_wp_error($post_id)) {
    http_response_code(500);
    echo json_encode(['success' => false, 'message' => $post_id->get_error_message()]);
    exit;
}

if ($cat_id) {
    wp_set_post_terms($post_id, [$cat_id], 'category');
}
if (!empty($tag_ids)) {
    wp_set_post_terms($post_id, $tag_ids, 'post_tag');
}
if ($featured_id) {
    set_post_thumbnail($post_id, $featured_id);
}

update_post_meta($post_id, 'rank_math_title', $rank_title);
update_post_meta($post_id, 'rank_math_description', $rank_desc);
update_post_meta($post_id, 'rank_math_focus_keyword', $rank_kw);

if (!empty($faq_schema)) {
    $clean_schema = preg_replace('#<script(.*?)>|</script>#is', '', $faq_schema);
    update_post_meta($post_id, '_ssi_schema_faq', wp_slash(trim($clean_schema)));
}

if ($lang !== '') {
    update_post_meta($post_id, '_kisan_lang', $lang);
    if (function_exists('pll_languages_list') && function_exists('pll_set_post_language')) {
        $valid_langs = pll_languages_list(['fields' => 'slug']);
        if (in_array($lang, $valid_langs, true)) {
            pll_set_post_language($post_id, $lang);
        }
    }
}

$post_url = get_permalink($post_id);
echo json_encode([
    'success' => true,
    'post_id' => (int) $post_id,
    'post_url' => $post_url,
    'status' => $status,
]);
