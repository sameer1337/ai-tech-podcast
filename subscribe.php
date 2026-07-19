<?php
// Mapt Daily / AI Tech Daily subscribe endpoint (Hostinger PHP).
// 1) Stores emails to subscribers.csv (backup you always own)
// 2) Notifies hello@mapt.cloud
// 3) Forwards the subscriber to beehiiv (the real newsletter list) if configured.
//
// beehiiv setup: create a publication, then Settings → API to get an API key,
// and copy the Publication ID (starts with "pub_"). Fill the two constants
// below OR set them as environment variables. Until then, beehiiv is skipped
// silently and CSV capture still works — nothing breaks.

header('Content-Type: text/plain; charset=utf-8');
header('Access-Control-Allow-Origin: *');

// ── beehiiv config (fill these once) ───────────────────────────────
$BEEHIIV_API_KEY = getenv('BEEHIIV_API_KEY') ?: '';        // e.g. "xxxxxxxx..."
$BEEHIIV_PUB_ID  = getenv('BEEHIIV_PUB_ID')  ?: '';        // e.g. "pub_xxxxxxxx-xxxx-..."
// ───────────────────────────────────────────────────────────────────

if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo 'method'; exit; }

$email  = isset($_POST['email'])  ? trim($_POST['email']) : '';
$source = isset($_POST['source']) ? preg_replace('/[^a-z0-9_\-]/i', '', $_POST['source']) : 'site';

if (!filter_var($email, FILTER_VALIDATE_EMAIL)) { http_response_code(400); echo 'invalid'; exit; }

// 1) Always keep our own backup copy of every signup.
$line = date('c') . "\t" . $email . "\t" . $source . "\t" . ($_SERVER['REMOTE_ADDR'] ?? '') . "\n";
@file_put_contents(__DIR__ . '/subscribers.csv', $line, FILE_APPEND | LOCK_EX);

// 2) Ping the owner (optional; harmless if mail() is disabled).
@mail('hello@mapt.cloud', 'New AI Tech Daily subscriber',
      "Email: $email\nSource: $source\nTime: " . date('c'),
      "From: no-reply@mapt.cloud\r\nContent-Type: text/plain; charset=utf-8");

// 3) Forward to beehiiv so the send list stays in sync automatically.
if ($BEEHIIV_API_KEY && $BEEHIIV_PUB_ID && function_exists('curl_init')) {
    $payload = json_encode([
        'email'              => $email,
        'reactivate_existing'=> false,
        'send_welcome_email' => true,
        'utm_source'         => 'daily.mapt.cloud',
        'utm_medium'         => $source,
        'referring_site'     => 'daily.mapt.cloud',
    ]);
    $ch = curl_init("https://api.beehiiv.com/v2/publications/{$BEEHIIV_PUB_ID}/subscriptions");
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => $payload,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 8,
        CURLOPT_HTTPHEADER     => [
            'Authorization: Bearer ' . $BEEHIIV_API_KEY,
            'Content-Type: application/json',
        ],
    ]);
    $resp = curl_exec($ch);
    $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    // Log failures for debugging but never block the user's signup.
    if ($code < 200 || $code >= 300) {
        @file_put_contents(__DIR__ . '/beehiiv_errors.log',
            date('c') . "\t$email\tHTTP $code\t$resp\n", FILE_APPEND | LOCK_EX);
    }
}

echo 'ok';
