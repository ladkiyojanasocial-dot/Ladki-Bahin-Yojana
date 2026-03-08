<?php
/**
 * Polylang REST API — Allow Kisan Portal Agent to set post language via REST.
 *
 * The FREE version of Polylang does NOT expose a "lang" field in the REST API
 * (that requires Polylang Pro). This snippet bridges the gap by:
 *   1. Registering a custom "lang" meta field on posts (readable + writable via REST).
 *   2. Hooking into rest_after_insert_post to call pll_set_post_language()
 *      whenever a post is created or updated via REST with a "lang" value.
 *
 * Installation:
 *   - Add this file's contents to your theme's functions.php, OR
 *   - Place the file in wp-content/mu-plugins/ (create the folder if needed).
 *
 * After adding: the agent's create_post() will automatically set the Polylang
 * language by including  "lang": "hi"  (or "en", "te") in the post JSON body.
 */

add_action( 'init', 'kisan_agent_register_polylang_lang_meta', 20 );

function kisan_agent_register_polylang_lang_meta() {
	register_post_meta(
		'post',
		'_kisan_lang',
		array(
			'show_in_rest'  => true,
			'single'        => true,
			'type'          => 'string',
			'auth_callback' => function() {
				return current_user_can( 'edit_posts' );
			},
		)
	);
}

/**
 * After a post is created/updated via REST, check for _kisan_lang meta
 * and set the Polylang language accordingly.
 */
add_action( 'rest_after_insert_post', 'kisan_agent_set_polylang_language', 10, 3 );

function kisan_agent_set_polylang_language( $post, $request, $creating ) {
	// Check if _kisan_lang was sent in the meta
	$params = $request->get_json_params();
	$lang   = '';

	// Look in meta._kisan_lang first
	if ( ! empty( $params['meta']['_kisan_lang'] ) ) {
		$lang = sanitize_text_field( $params['meta']['_kisan_lang'] );
	}

	// Skip if no language specified or Polylang not active
	if ( empty( $lang ) || ! function_exists( 'pll_set_post_language' ) ) {
		return;
	}

	// Validate against configured Polylang languages
	if ( function_exists( 'pll_languages_list' ) ) {
		$valid_langs = pll_languages_list( array( 'fields' => 'slug' ) );
		if ( ! in_array( $lang, $valid_langs, true ) ) {
			return; // Invalid language slug — do nothing
		}
	}

	pll_set_post_language( $post->ID, $lang );
}
