<?php
/**
 * Plugin Name: SiteOps Agent
 * Description: Kết nối với SiteOps để kiểm tra tính toàn vẹn và dấu hiệu rủi ro của plugin.
 * Version: 1.0.0
 * Requires at least: 5.6
 * Requires PHP: 7.4
 * Author: SiteOps
 * License: GPL-2.0-or-later
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

define( 'SITEOPS_AGENT_VERSION', '1.0.0' );

add_action(
    'rest_api_init',
    static function () {
        register_rest_route(
            'siteops/v1',
            '/security/plugins',
            array(
                'methods'             => WP_REST_Server::CREATABLE,
                'callback'            => 'siteops_agent_scan_plugins',
                'permission_callback' => static function () {
                    return current_user_can( 'manage_options' );
                },
            )
        );
    }
);

/**
 * Quét ở chế độ chỉ đọc. Endpoint không trả nội dung mã nguồn.
 */
function siteops_agent_scan_plugins() {
    if ( ! function_exists( 'get_plugins' ) ) {
        require_once ABSPATH . 'wp-admin/includes/plugin.php';
    }

    $results = array();
    foreach ( get_plugins() as $plugin_file => $plugin_data ) {
        $results[] = siteops_agent_scan_plugin( $plugin_file, $plugin_data );
    }

    return rest_ensure_response(
        array(
            'agentVersion'     => SITEOPS_AGENT_VERSION,
            'wordpressVersion' => get_bloginfo( 'version' ),
            'phpVersion'       => PHP_VERSION,
            'scannedAt'        => current_time( 'c', true ),
            'plugins'          => $results,
            'summary'          => array(
                'total'    => count( $results ),
                'verified' => count( array_filter( $results, static fn( $item ) => 'verified' === $item['integrity'] ) ),
                'modified' => count( array_filter( $results, static fn( $item ) => 'modified' === $item['integrity'] ) ),
                'warning'  => count( array_filter( $results, static fn( $item ) => in_array( $item['risk'], array( 'medium', 'high' ), true ) ) ),
                'unknown'  => count( array_filter( $results, static fn( $item ) => 'unknown' === $item['integrity'] ) ),
            ),
        )
    );
}

function siteops_agent_scan_plugin( $plugin_file, $plugin_data ) {
    $version    = isset( $plugin_data['Version'] ) ? (string) $plugin_data['Version'] : '';
    $directory  = dirname( $plugin_file );
    $slug       = '.' === $directory ? sanitize_key( basename( $plugin_file, '.php' ) ) : sanitize_key( $directory );
    $plugin_dir = '.' === $directory ? WP_PLUGIN_DIR : WP_PLUGIN_DIR . '/' . $directory;
    $files      = '.' === $directory
        ? array( basename( $plugin_file ) => WP_PLUGIN_DIR . '/' . $plugin_file )
        : siteops_agent_list_files( $plugin_dir );
    $checksums  = siteops_agent_get_checksums( $slug, $version );
    $findings   = array();
    $modified   = array();
    $missing    = array();
    $unexpected = array();

    if ( is_array( $checksums ) ) {
        foreach ( $checksums as $relative => $expected_data ) {
            $full_path = trailingslashit( $plugin_dir ) . ltrim( $relative, '/' );
            if ( ! is_file( $full_path ) ) {
                $missing[] = $relative;
                continue;
            }

            $expected  = is_array( $expected_data ) ? ( $expected_data['sha256'] ?? $expected_data['md5'] ?? '' ) : $expected_data;
            $algorithm = 64 === strlen( $expected ) ? 'sha256' : 'md5';
            if ( $expected && ! hash_equals( strtolower( $expected ), strtolower( hash_file( $algorithm, $full_path ) ) ) ) {
                $modified[] = $relative;
            }
        }

        foreach ( $files as $relative => $full_path ) {
            if ( ! isset( $checksums[ $relative ] ) && 'php' === strtolower( pathinfo( $relative, PATHINFO_EXTENSION ) ) ) {
                $unexpected[] = $relative;
            }
        }
    }

    $code_signals = 'siteops-agent' === $slug ? array() : siteops_agent_scan_code_signals( $files );
    if ( $modified ) {
        $findings[] = count( $modified ) . ' file không khớp checksum chính thức.';
    }
    if ( $missing ) {
        $findings[] = count( $missing ) . ' file chính thức bị thiếu.';
    }
    if ( $unexpected ) {
        $findings[] = count( $unexpected ) . ' file PHP không có trong bản phát hành chính thức.';
    }
    if ( $code_signals ) {
        $findings[] = count( $code_signals ) . ' dấu hiệu mã cần kiểm tra thủ công.';
    }

    $integrity = null === $checksums ? 'unknown' : ( $modified || $missing || $unexpected ? 'modified' : 'verified' );
    $risk      = 'low';
    if ( 'modified' === $integrity || siteops_agent_has_high_signal( $code_signals ) ) {
        $risk = 'high';
    } elseif ( $code_signals ) {
        $risk = 'medium';
    } elseif ( 'unknown' === $integrity ) {
        $risk = 'unknown';
    }

    return array(
        'plugin'        => $plugin_file,
        'slug'          => $slug,
        'name'          => wp_strip_all_tags( $plugin_data['Name'] ?? $plugin_file ),
        'version'       => $version,
        'active'        => is_plugin_active( $plugin_file ),
        'source'        => null === $checksums ? 'third-party-or-custom' : 'wordpress.org',
        'licenseStatus' => null === $checksums ? 'unknown' : 'not-required',
        'integrity'     => $integrity,
        'risk'          => $risk,
        'findings'      => $findings,
        'changedFiles'  => array_slice( array_values( array_unique( array_merge( $modified, $missing, $unexpected ) ) ), 0, 30 ),
        'codeSignals'   => array_slice( $code_signals, 0, 30 ),
    );
}

function siteops_agent_get_checksums( $slug, $version ) {
    if ( ! $slug || ! $version ) {
        return null;
    }

    $cache_key = 'siteops_checksum_' . md5( $slug . ':' . $version );
    $cached    = get_transient( $cache_key );
    if ( is_array( $cached ) ) {
        return $cached;
    }

    $url      = sprintf( 'https://downloads.wordpress.org/plugin-checksums/%s/%s.json', rawurlencode( $slug ), rawurlencode( $version ) );
    $response = wp_safe_remote_get( $url, array( 'timeout' => 15, 'redirection' => 2 ) );
    if ( is_wp_error( $response ) || 200 !== wp_remote_retrieve_response_code( $response ) ) {
        return null;
    }

    $payload = json_decode( wp_remote_retrieve_body( $response ), true );
    if ( isset( $payload['files'] ) && is_array( $payload['files'] ) ) {
        set_transient( $cache_key, $payload['files'], 12 * HOUR_IN_SECONDS );
        return $payload['files'];
    }
    return null;
}

function siteops_agent_list_files( $root ) {
    $files = array();
    if ( ! is_dir( $root ) ) {
        return $files;
    }

    try {
        $iterator = new RecursiveIteratorIterator( new RecursiveDirectoryIterator( $root, FilesystemIterator::SKIP_DOTS ) );
        foreach ( $iterator as $file ) {
            if ( ! $file->isFile() || count( $files ) >= 5000 ) {
                continue;
            }
            $full_path          = wp_normalize_path( $file->getPathname() );
            $relative           = ltrim( substr( $full_path, strlen( wp_normalize_path( trailingslashit( $root ) ) ) ), '/' );
            $files[ $relative ] = $full_path;
        }
    } catch ( UnexpectedValueException $error ) {
        return $files;
    }

    return $files;
}

function siteops_agent_scan_code_signals( $files ) {
    $patterns = array(
        'obfuscated-eval' => array( 'level' => 'high', 'regex' => '/eval\s*\(\s*base64_decode\s*\(/i' ),
        'encoded-payload' => array( 'level' => 'medium', 'regex' => '/(?:gzinflate|gzuncompress)\s*\(\s*base64_decode\s*\(/i' ),
        'request-exec'    => array( 'level' => 'high', 'regex' => '/(?:eval|assert|system|passthru|shell_exec)\s*\(\s*\$_(?:GET|POST|REQUEST|COOKIE)/i' ),
        'license-bypass'  => array( 'level' => 'medium', 'regex' => '/(?:bypass|disable|skip)[_-]?(?:license|activation)|nulled|cracked/i' ),
    );
    $signals = array();

    foreach ( $files as $relative => $full_path ) {
        if ( 'php' !== strtolower( pathinfo( $relative, PATHINFO_EXTENSION ) ) || filesize( $full_path ) > 2 * MB_IN_BYTES ) {
            continue;
        }
        $contents = file_get_contents( $full_path );
        if ( false === $contents ) {
            continue;
        }
        foreach ( $patterns as $type => $pattern ) {
            if ( preg_match( $pattern['regex'], $contents ) ) {
                $signals[] = array( 'type' => $type, 'level' => $pattern['level'], 'file' => $relative );
            }
        }
    }

    return $signals;
}

function siteops_agent_has_high_signal( $signals ) {
    foreach ( $signals as $signal ) {
        if ( 'high' === $signal['level'] ) {
            return true;
        }
    }
    return false;
}
