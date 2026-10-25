<?php
/**
 * Plugin Name:       DigiByte DigiFacts
 * Plugin URI:        https://github.com/DigiNode-Tools/digibyte-digifacts/tree/main/wordpress
 * Description:       Show a random DigiFact - a bite-size fact about DigiByte - that changes every minute. Available in multiple languages.
 * Version:           2.2.4
 * Requires at least: 5.0
 * Requires PHP:      7.4
 * Author:            Olly Stedall (DigiNode Tools)
 * Author URI:        https://diginode.tools
 * License:           GPL-2.0-or-later
 * License URI:       https://www.gnu.org/licenses/gpl-2.0.html
 * Text Domain:       digibyte-digifacts
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

const DIGIBYTE_DIGIFACTS_VERSION = '2.2.4';
// The DigiFacts website (https://github.com/DigiNode-Tools/digibyte-digifacts). Updated hourly.
const DIGIBYTE_DIGIFACTS_URL = 'https://digifacts.diginode.tools';
const DIGIBYTE_DIGIFACTS_REPO = 'https://github.com/DigiNode-Tools/digibyte-digifacts';
const DIGIBYTE_DIGIFACTS_SPONSOR = 'https://diginode.tools/sponsors/';

/**
 * Fetch a JSON file from the DigiFacts website. Each file is checked at most once an hour. If it can't be fetched,
 * the last good copy is used (and checked again in 10 minutes). Returns null if there has never been a good copy.
 *
 * @param string $path     e.g. 'en/html.json'
 * @param string $cache_id Short name for the cache, e.g. 'facts_en'
 */
function digibyte_digifacts_get_json( $path, $cache_id ) {
	$transient = 'digibyte_digifacts_' . $cache_id;
	$cached    = get_transient( $transient );
	if ( false !== $cached ) {
		return $cached ? $cached : null;
	}

	$data     = null;
	$response = wp_remote_get( DIGIBYTE_DIGIFACTS_URL . '/' . $path, array( 'timeout' => 5 ) );
	if ( ! is_wp_error( $response ) && 200 === wp_remote_retrieve_response_code( $response ) ) {
		$decoded = json_decode( wp_remote_retrieve_body( $response ), true );
		if ( is_array( $decoded ) && $decoded ) {
			$data = $decoded;
			update_option( $transient . '_last_good', $data, false );
		}
	}
	if ( ! $data ) {
		$data = get_option( $transient . '_last_good', null );
	}

	set_transient( $transient, $data ? $data : array(), $data ? HOUR_IN_SECONDS : 10 * MINUTE_IN_SECONDS );
	return $data;
}

/**
 * The available languages, as code => name (English first), from the DigiFacts website's info.json.
 */
function digibyte_digifacts_languages() {
	$info  = digibyte_digifacts_get_json( 'info.json', 'info' );
	$langs = array();
	if ( isset( $info['languages'] ) && is_array( $info['languages'] ) ) {
		foreach ( $info['languages'] as $code => $lang ) {
			if ( preg_match( '/^[a-z]{2}(-[a-z]{2,4})?$/', $code ) ) {
				$langs[ $code ] = isset( $lang['name'] ) ? (string) $lang['name'] : $code;
			}
		}
	}
	return $langs ? $langs : array( 'en' => 'English' );
}

/**
 * The topic tags DigiFacts can have, as tag => description (e.g. 'your-project' => 'About Your Project').
 */
function digibyte_digifacts_tags() {
	$info = digibyte_digifacts_get_json( 'info.json', 'info' );
	$tags = array();
	if ( isset( $info['tags'] ) && is_array( $info['tags'] ) ) {
		foreach ( $info['tags'] as $tag => $details ) {
			if ( preg_match( '/^[a-z0-9]+(-[a-z0-9]+)*$/', $tag ) ) {
				$tags[ $tag ] = isset( $details['description'] ) ? (string) $details['description'] : $tag;
			}
		}
	}
	return $tags;
}

/**
 * The DigiFact IDs to hide, from the "Hide DigiFacts" setting (e.g. array( 'digifact-7ttm' )).
 */
function digibyte_digifacts_hidden_ids() {
	return digibyte_digifacts_parse_ids( get_option( 'digibyte_digifacts_hide_ids', '' ) );
}

/**
 * The valid DigiFact IDs in a comma-separated list, e.g. 'digifact-7ttm, gsz3' => array( 'digifact-7ttm', 'digifact-gsz3' ).
 */
function digibyte_digifacts_parse_ids( $text ) {
	$ids = array();
	foreach ( preg_split( '/[\s,]+/', strtolower( (string) $text ) ) as $id ) {
		if ( preg_match( '/^(digifact-)?([a-z0-9]{4})$/', $id, $m ) ) {
			$ids[] = 'digifact-' . $m[2];
		}
	}
	return array_values( array_unique( $ids ) );
}

/**
 * The DigiFacts for a language, ready to show: a list of array( 'title' => text, 'content' => safe HTML ).
 * Falls back to English if the language isn't available. DigiFacts hidden in the settings (by ID or topic) are left out.
 */
function digibyte_digifacts_facts( $language ) {
	if ( ! preg_match( '/^[a-z]{2}(-[a-z]{2,4})?$/', $language ) ) {
		$language = 'en';
	}
	$raw = digibyte_digifacts_get_json( $language . '/html.json', 'facts_' . $language );
	if ( ! $raw && 'en' !== $language ) {
		$raw = digibyte_digifacts_get_json( 'en/html.json', 'facts_en' );
	}
	if ( ! is_array( $raw ) ) {
		return array();
	}

	// Only a link is allowed in a DigiFact (the DigiFacts website checks this too)
	$allowed = array(
		'a' => array(
			'href'   => true,
			'target' => true,
			'rel'    => true,
		),
	);
	$hide_ids  = digibyte_digifacts_hidden_ids();
	$hide_tags = (array) get_option( 'digibyte_digifacts_hide_tags', array() );
	$facts     = array();
	foreach ( $raw as $id => $fact ) {
		if ( ! is_array( $fact ) || empty( $fact['title'] ) || empty( $fact['content'] ) ) {
			continue;
		}
		$fact_id   = isset( $fact['id'] ) ? (string) $fact['id'] : (string) $id;
		$fact_tags = isset( $fact['tags'] ) && is_array( $fact['tags'] ) ? $fact['tags'] : array();
		if ( in_array( strtolower( $fact_id ), $hide_ids, true ) || array_intersect( $fact_tags, $hide_tags ) ) {
			continue; // Hidden on this site
		}
		$content = wp_kses( (string) $fact['content'], $allowed );
		$content = str_replace( 'target="_blank"', 'target="_blank" rel="noopener"', $content );
		$facts[] = array(
			'title'   => wp_strip_all_tags( (string) $fact['title'] ),
			'content' => $content,
		);
	}
	return $facts;
}

/**
 * The DigiFacts this site hides, for the browser console: array( 'hidden' => list of array( 'number', 'id', 'why',
 * 'text' ) in English, 'total' => the number of DigiFacts ).
 */
function digibyte_digifacts_hidden_list() {
	$raw = digibyte_digifacts_get_json( 'en/html.json', 'facts_en' );
	if ( ! is_array( $raw ) ) {
		return array();
	}
	$hide_ids  = digibyte_digifacts_hidden_ids();
	$hide_tags = (array) get_option( 'digibyte_digifacts_hide_tags', array() );
	$hidden    = array();
	$number    = 0;
	foreach ( $raw as $id => $fact ) {
		if ( ! is_array( $fact ) || empty( $fact['content'] ) ) {
			continue;
		}
		++$number;
		$fact_id   = isset( $fact['id'] ) ? (string) $fact['id'] : (string) $id;
		$fact_tags = isset( $fact['tags'] ) && is_array( $fact['tags'] ) ? $fact['tags'] : array();
		$why       = array();
		if ( in_array( strtolower( $fact_id ), $hide_ids, true ) ) {
			$why[] = 'ID';
		}
		foreach ( array_intersect( $fact_tags, $hide_tags ) as $tag ) {
			$why[] = 'topic ' . $tag;
		}
		if ( $why ) {
			$text     = wp_strip_all_tags( (string) $fact['content'] );
			$hidden[] = array(
				'number' => $number,
				'id'     => $fact_id,
				'why'    => implode( ', ', $why ),
				'text'   => mb_strlen( $text ) > 80 ? mb_substr( $text, 0, 80 ) . '...' : $text,
			);
		}
	}
	return array( 'hidden' => $hidden, 'total' => $number );
}

/**
 * [digifacts] - shows a random DigiFact, which changes every minute.
 */
function digibyte_digifacts_shortcode() {
	$setting = get_option( 'digibyte_digifacts_language', 'en' );
	// "Visitor's language": the page shows English, and the script switches to the visitor's language if available
	$language = 'auto' === $setting ? 'en' : $setting;
	$facts    = digibyte_digifacts_facts( $language );
	if ( ! $facts ) {
		return ''; // Show nothing rather than an error
	}

	$fact = $facts[ array_rand( $facts ) ];
	$box  = 'text' !== get_option( 'digibyte_digifacts_display', 'box' );

	wp_enqueue_style( 'digibyte-digifacts' );
	wp_enqueue_script( 'digibyte-digifacts' );
	digibyte_digifacts_print_facts_once( $facts, $language, 'auto' === $setting );

	return '<div class="digibyte-digifact' . ( $box ? ' with-box' : ' without-box' ) . '">'
		. '<h5 class="digifact-title">' . esc_html( $fact['title'] ) . '</h5>'
		. '<div class="digifact-content">' . $fact['content'] . '</div>'
		. ( 'no' !== get_option( 'digibyte_digifacts_credit', 'yes' )
			? '<p class="digifact-credit"><a href="' . esc_url( DIGIBYTE_DIGIFACTS_URL . '/' ) . '" target="_blank" rel="noopener">About DigiByte DigiFacts</a></p>'
			: '' )
		. '</div>';
}
add_shortcode( 'digifacts', 'digibyte_digifacts_shortcode' );

/**
 * Add the facts to the page once (for the script that changes the DigiFact every minute). Included in the page, so
 * it works with page caching and visitors' browsers don't need to contact any other site.
 */
function digibyte_digifacts_print_facts_once( $facts, $language, $auto ) {
	static $done = false;
	if ( $done ) {
		return;
	}
	$done   = true;
	$flags  = JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT;
	$config = array(
		'language'  => $language,
		'auto'      => (bool) $auto,
		'languages' => array_keys( digibyte_digifacts_languages() ),
		'url'       => esc_url_raw( rest_url( 'digibyte-digifacts/v1/facts/' ) ),
		'hidden'    => digibyte_digifacts_hidden_list(),
	);
	wp_add_inline_script(
		'digibyte-digifacts',
		'window.digibyteDigiFacts = ' . wp_json_encode( $facts, $flags ) . '; window.digibyteDigiFactsConfig = ' . wp_json_encode( $config, $flags ) . ';',
		'before'
	);
}

/**
 * The DigiFacts in one language, for the "Visitor's language" option: /wp-json/digibyte-digifacts/v1/facts/de
 * Served from this site (cached for an hour), so visitors' browsers don't contact any other site.
 */
function digibyte_digifacts_rest_routes() {
	register_rest_route(
		'digibyte-digifacts/v1',
		'/facts/(?P<language>[a-z]{2}(-[a-z]{2,4})?)',
		array(
			'methods'             => 'GET',
			'permission_callback' => '__return_true',
			'callback'            => function ( $request ) {
				$language = $request['language'];
				if ( ! array_key_exists( $language, digibyte_digifacts_languages() ) ) {
					return new WP_Error( 'digifacts_language', 'This language is not available.', array( 'status' => 404 ) );
				}
				$response = rest_ensure_response( digibyte_digifacts_facts( $language ) );
				$response->header( 'Cache-Control', 'public, max-age=3600' );
				return $response;
			},
		)
	);
}
add_action( 'rest_api_init', 'digibyte_digifacts_rest_routes' );

function digibyte_digifacts_register_assets() {
	wp_register_style( 'digibyte-digifacts', plugins_url( 'digifacts-styles.css', __FILE__ ), array(), DIGIBYTE_DIGIFACTS_VERSION );
	wp_register_script( 'digibyte-digifacts', plugins_url( 'js/digifact-refresh.js', __FILE__ ), array(), DIGIBYTE_DIGIFACTS_VERSION, true );
}
// Registered early ('init'), because block themes render the page content before 'wp_enqueue_scripts'
add_action( 'init', 'digibyte_digifacts_register_assets' );

/**
 * The stylesheet (under 1 KB) is loaded in the page's <head> on every page, before the theme's and the site's own
 * CSS (Appearance > Customize > Additional CSS) - so their CSS can change how the DigiFacts look. (Loaded later, only
 * when a DigiFact is shown, it would come after the site's CSS and override it.)
 */
function digibyte_digifacts_enqueue_style() {
	wp_enqueue_style( 'digibyte-digifacts' );
}
add_action( 'wp_enqueue_scripts', 'digibyte_digifacts_enqueue_style', 5 );

/**
 * The DigiFacts block (shows the same as the shortcode).
 */
function digibyte_digifacts_register_block() {
	wp_register_script( 'digibyte-digifacts-block', plugins_url( 'js/block.js', __FILE__ ), array( 'wp-blocks', 'wp-element' ), DIGIBYTE_DIGIFACTS_VERSION, true );
	register_block_type(
		'digibyte/digifacts',
		array(
			'editor_script'   => 'digibyte-digifacts-block',
			'render_callback' => 'digibyte_digifacts_shortcode',
		)
	);
}
add_action( 'init', 'digibyte_digifacts_register_block' );

/*
 * Settings page: Settings > DigiFacts
 */

function digibyte_digifacts_admin_menu() {
	add_options_page( 'DigiByte DigiFacts', 'DigiFacts', 'manage_options', 'digibyte-digifacts', 'digibyte_digifacts_settings_page' );
}
add_action( 'admin_menu', 'digibyte_digifacts_admin_menu' );

function digibyte_digifacts_settings_init() {
	register_setting(
		'digibyte_digifacts_options',
		'digibyte_digifacts_language',
		array(
			'type'              => 'string',
			'default'           => 'en',
			'sanitize_callback' => 'digibyte_digifacts_sanitize_language',
		)
	);
	register_setting(
		'digibyte_digifacts_options',
		'digibyte_digifacts_display',
		array(
			'type'              => 'string',
			'default'           => 'box',
			'sanitize_callback' => 'digibyte_digifacts_sanitize_display',
		)
	);
	register_setting(
		'digibyte_digifacts_options',
		'digibyte_digifacts_credit',
		array(
			'type'              => 'string',
			'default'           => 'yes',
			'sanitize_callback' => 'digibyte_digifacts_sanitize_credit',
		)
	);
	register_setting(
		'digibyte_digifacts_options',
		'digibyte_digifacts_hide_tags',
		array(
			'type'              => 'array',
			'default'           => array(),
			'sanitize_callback' => 'digibyte_digifacts_sanitize_hide_tags',
		)
	);
	register_setting(
		'digibyte_digifacts_options',
		'digibyte_digifacts_hide_ids',
		array(
			'type'              => 'string',
			'default'           => '',
			'sanitize_callback' => 'digibyte_digifacts_sanitize_hide_ids',
		)
	);
	add_settings_section( 'digibyte_digifacts_section', '', '__return_false', 'digibyte-digifacts' );
	add_settings_field( 'digibyte_digifacts_language', 'Language', 'digibyte_digifacts_language_field', 'digibyte-digifacts', 'digibyte_digifacts_section' );
	add_settings_field( 'digibyte_digifacts_display', 'Display', 'digibyte_digifacts_display_field', 'digibyte-digifacts', 'digibyte_digifacts_section' );
	add_settings_field( 'digibyte_digifacts_hide_tags', 'Hide topics', 'digibyte_digifacts_hide_tags_field', 'digibyte-digifacts', 'digibyte_digifacts_section' );
	add_settings_field( 'digibyte_digifacts_hide_ids', 'Hide DigiFacts', 'digibyte_digifacts_hide_ids_field', 'digibyte-digifacts', 'digibyte_digifacts_section' );
}
add_action( 'admin_init', 'digibyte_digifacts_settings_init' );

function digibyte_digifacts_sanitize_language( $code ) {
	if ( 'auto' === $code ) {
		return 'auto';
	}
	return array_key_exists( $code, digibyte_digifacts_languages() ) ? $code : 'en';
}

function digibyte_digifacts_sanitize_display( $display ) {
	return 'text' === $display ? 'text' : 'box';
}

function digibyte_digifacts_sanitize_credit( $credit ) {
	return 'yes' === $credit ? 'yes' : 'no';
}

function digibyte_digifacts_sanitize_hide_tags( $tags ) {
	// Typed, separated by commas (or a list, from older versions' checkboxes)
	$tags = is_array( $tags ) ? $tags : preg_split( '/[\s,]+/', strtolower( (string) $tags ) );
	return array_values( array_unique( array_filter( $tags, function ( $tag ) {
		return (bool) preg_match( '/^[a-z0-9]+(-[a-z0-9]+)*$/', $tag );
	} ) ) );
}

function digibyte_digifacts_sanitize_hide_ids( $ids ) {
	return implode( ', ', digibyte_digifacts_parse_ids( $ids ) );
}

function digibyte_digifacts_hide_tags_field() {
	$hidden = (array) get_option( 'digibyte_digifacts_hide_tags', array() );
	printf(
		'<input type="text" class="regular-text" name="digibyte_digifacts_hide_tags" value="%s" placeholder="your-project" />',
		esc_attr( implode( ', ', $hidden ) )
	);
	echo '<p class="description">If your site or project is mentioned in some DigiFacts, hide them here - your visitors are already on your site. Type your project\'s topic (separate several with commas). New DigiFacts with that topic are hidden too. Each DigiFact\'s topic is shown next to it on the <a href="https://digifacts.diginode.tools/proofread/en/" target="_blank" rel="noopener">DigiFacts proofreading pages</a>. If your project doesn\'t have a topic yet, <a href="https://github.com/DigiNode-Tools/digibyte-digifacts/issues/new" target="_blank" rel="noopener">ask for one</a>.</p>';
	// Confirm what each typed topic is, so a typo is easy to spot
	$tags = digibyte_digifacts_tags();
	foreach ( $hidden as $tag ) {
		if ( isset( $tags[ $tag ] ) ) {
			printf( '<p class="description">&#10003; <code>%s</code>: %s</p>', esc_html( $tag ), esc_html( $tags[ $tag ] ) );
		} elseif ( $tags ) {
			printf( '<p class="description">&#9888; <code>%s</code> isn\'t a DigiFacts topic (yet) - check the spelling.</p>', esc_html( $tag ) );
		}
	}
}

function digibyte_digifacts_hide_ids_field() {
	printf(
		'<input type="text" class="regular-text" name="digibyte_digifacts_hide_ids" value="%s" placeholder="digifact-7ttm, digifact-gsz3" />',
		esc_attr( get_option( 'digibyte_digifacts_hide_ids', '' ) )
	);
	echo '<p class="description">To hide single DigiFacts about your site or project, enter their IDs, separated by commas. (Hiding a topic above is usually easier.) Each DigiFact\'s ID is shown on the <a href="https://digifacts.diginode.tools/proofread/en/" target="_blank" rel="noopener">DigiFacts proofreading pages</a>. IDs never change (unlike DigiFact numbers).</p>';
}

function digibyte_digifacts_language_field() {
	$current = get_option( 'digibyte_digifacts_language', 'en' );
	echo '<select id="digibyte_digifacts_language" name="digibyte_digifacts_language">';
	printf( '<option value="auto"%s>Visitor\'s language (automatic)</option>', selected( $current, 'auto', false ) );
	foreach ( digibyte_digifacts_languages() as $code => $name ) {
		printf( '<option value="%s"%s>%s</option>', esc_attr( $code ), selected( $current, $code, false ), esc_html( $name ) );
	}
	echo '</select>';
	echo '<p class="description">"Visitor\'s language" shows each visitor the DigiFacts in their browser\'s language, if available (otherwise English). A DigiFact that isn\'t translated yet is shown in English.</p>';
}

function digibyte_digifacts_display_field() {
	$display = get_option( 'digibyte_digifacts_display', 'box' );
	?>
	<label><input type="radio" name="digibyte_digifacts_display" value="box" <?php checked( $display, 'box' ); ?> /> Box</label><br />
	<label><input type="radio" name="digibyte_digifacts_display" value="text" <?php checked( $display, 'text' ); ?> /> Text only</label>
	<p>
		<input type="hidden" name="digibyte_digifacts_credit" value="no" />
		<label><input type="checkbox" name="digibyte_digifacts_credit" value="yes" <?php checked( 'no' !== get_option( 'digibyte_digifacts_credit', 'yes' ) ); ?> /> Show a small "About DigiByte DigiFacts" link under the DigiFact</label>
	</p>
	<?php
}

function digibyte_digifacts_settings_page() {
	if ( ! current_user_can( 'manage_options' ) ) {
		return;
	}
	delete_transient( 'digibyte_digifacts_info' ); // Fresh languages and topics on the settings page
	$facts = digibyte_digifacts_facts( get_option( 'digibyte_digifacts_language', 'en' ) );
	?>
	<div class="wrap">
		<h1>DigiByte DigiFacts</h1>
		<?php if ( ! $facts ) : ?>
			<div class="notice notice-warning"><p>The DigiFacts can't be loaded from <?php echo esc_html( DIGIBYTE_DIGIFACTS_URL ); ?> at the moment, so nothing is shown on your site. This is checked again every 10 minutes.</p></div>
		<?php endif; ?>
		<form action="options.php" method="post">
			<?php
			settings_fields( 'digibyte_digifacts_options' );
			do_settings_sections( 'digibyte-digifacts' );
			submit_button();
			?>
		</form>

		<h2>Usage</h2>
		<p>Add the <code>[digifacts]</code> shortcode, or the DigiByte DigiFacts block, where you want a DigiFact to appear. A random DigiFact is shown, and it changes every minute.</p>

		<h2>Styling</h2>
		<p>The DigiFacts use your theme's fonts and colours. To change how they look, add CSS in Appearance &gt; Customize &gt; Additional CSS. For example:</p>
		<pre>.digibyte-digifact .digifact-title { font-size: 1.2em; }
.digibyte-digifact.with-box { border-color: #0066cc; background: #f4f8ff; }
.digibyte-digifact .digifact-credit a { color: #0066cc; }</pre>

		<h2>Help improve the DigiFacts</h2>
		<p>Spotted a mistake, or a DigiFact that's out of date? Corrections, new DigiFacts and translations are all welcome - see <a href="<?php echo esc_url( DIGIBYTE_DIGIFACTS_REPO ); ?>" target="_blank" rel="noopener">how to contribute</a>.</p>
		<p>DigiFacts are maintained by <a href="https://diginode.tools" target="_blank" rel="noopener">DigiNode Tools</a>. If you find them useful, please consider <a href="<?php echo esc_url( DIGIBYTE_DIGIFACTS_SPONSOR ); ?>" target="_blank" rel="noopener">sponsoring DigiNode Tools</a>.</p>
	</div>
	<?php
}

/**
 * Clear the cached DigiFacts when the settings are saved, so changes (e.g. hiding a topic) apply straight away.
 */
function digibyte_digifacts_clear_cache() {
	delete_transient( 'digibyte_digifacts_info' );
	foreach ( array_keys( digibyte_digifacts_languages() ) as $code ) {
		delete_transient( 'digibyte_digifacts_facts_' . $code );
	}
}
foreach ( array( 'language', 'hide_tags', 'hide_ids' ) as $digibyte_digifacts_option ) {
	add_action( 'update_option_digibyte_digifacts_' . $digibyte_digifacts_option, 'digibyte_digifacts_clear_cache' );
	add_action( 'add_option_digibyte_digifacts_' . $digibyte_digifacts_option, 'digibyte_digifacts_clear_cache' );
}

/**
 * Tidy up after version 1.x (its browser cache and old options are no longer used).
 */
function digibyte_digifacts_upgrade() {
	if ( get_option( 'digibyte_digifacts_version' ) === DIGIBYTE_DIGIFACTS_VERSION ) {
		return;
	}
	delete_option( 'digibyte_digifacts_languages' );
	delete_transient( 'digibyte_digifacts_language_changed' );
	foreach ( array_keys( digibyte_digifacts_languages() ) as $code ) {
		delete_transient( 'digibyte_digifacts_' . $code ); // 1.x cache (old format)
	}
	update_option( 'digibyte_digifacts_version', DIGIBYTE_DIGIFACTS_VERSION );
}
add_action( 'admin_init', 'digibyte_digifacts_upgrade' );
