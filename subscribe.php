<?php
// Mapt Daily newsletter subscribe endpoint (Hostinger PHP).
// Stores emails to subscribers.csv and notifies hello@mapt.cloud.
header('Content-Type: text/plain; charset=utf-8');
header('Access-Control-Allow-Origin: *');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo 'method'; exit; }

$email  = isset($_POST['email'])  ? trim($_POST['email']) : '';
$source = isset($_POST['source']) ? preg_replace('/[^a-z0-9_\-]/i', '', $_POST['source']) : 'site';

if (!filter_var($email, FILTER_VALIDATE_EMAIL)) { http_response_code(400); echo 'invalid'; exit; }

$line = date('c') . "\t" . $email . "\t" . $source . "\t" . ($_SERVER['REMOTE_ADDR'] ?? '') . "\n";
@file_put_contents(__DIR__ . '/subscribers.csv', $line, FILE_APPEND | LOCK_EX);

@mail('hello@mapt.cloud', 'New Mapt Daily subscriber',
      "Email: $email\nSource: $source\nTime: " . date('c'),
      "From: no-reply@mapt.cloud\r\nContent-Type: text/plain; charset=utf-8");

echo 'ok';
