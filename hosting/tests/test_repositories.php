<?php

declare(strict_types=1);

use Hosting\Model\DatabaseRepository;
use Hosting\Model\DatabaseUserRepository;
use Hosting\Model\JobRepository;
use Hosting\Model\PlanRepository;
use Hosting\Model\SiteRepository;
use Hosting\Model\UserRepository;

function test_repo_plans_seeded_by_schema(): void
{
    $db = hosting_test_db();
    $plans = new PlanRepository($db);

    $all = $plans->all();
    assert_equals(3, count($all), 'Ожидались 3 тарифа из схемы');
    assert_true($plans->findByCode('start') !== null);
    assert_true($plans->findByCode('nonexistent') === null);
}

function test_repo_user_registration_assigns_system_user(): void
{
    $db = hosting_test_db();
    $users = new UserRepository($db, new PlanRepository($db));

    $user = $users->create('client@example.com', 'password123', 'start');

    assert_equals('client1001', $user['system_user']);
    assert_equals('active', $user['status']);
    assert_equals(2048, (int) $user['disk_quota_mb']);
}

function test_repo_user_duplicate_email_rejected(): void
{
    $db = hosting_test_db();
    $users = new UserRepository($db, new PlanRepository($db));
    $users->create('dup@example.com', 'password123', 'start');

    assert_throws(static function () use ($users): void {
        $users->create('dup@example.com', 'password123', 'start');
    }, 'Повторная регистрация с тем же e-mail должна быть отклонена');
}

function test_repo_user_short_password_rejected(): void
{
    $db = hosting_test_db();
    $users = new UserRepository($db, new PlanRepository($db));

    assert_throws(static function () use ($users): void {
        $users->create('short@example.com', '1234567', 'start');
    }, 'Пароль короче 8 символов должен быть отклонён');
}

function test_repo_site_creation_and_lookup(): void
{
    $db = hosting_test_db();
    $users = new UserRepository($db, new PlanRepository($db));
    $sites = new SiteRepository($db);

    $user = $users->create('siteowner@example.com', 'password123', 'start');
    $site = $sites->create((int) $user['id'], 'shop', 'shop.myhost.tj', '8.3');

    assert_equals('pending', $site['status']);
    assert_equals(1, $sites->countActiveForUser((int) $user['id']));

    $found = $sites->findByDomain('shop.myhost.tj');
    assert_true($found !== null);
    assert_equals((int) $user['id'], (int) $found['user_id']);
}

function test_repo_site_idor_ownership_check(): void
{
    $db = hosting_test_db();
    $users = new UserRepository($db, new PlanRepository($db));
    $sites = new SiteRepository($db);

    $owner = $users->create('owner@example.com', 'password123', 'start');
    $stranger = $users->create('stranger@example.com', 'password123', 'start');
    $site = $sites->create((int) $owner['id'], 'shop', 'shop2.myhost.tj', '8.3');

    assert_true(SiteRepository::belongsToUser($site, (int) $owner['id']));
    assert_false(SiteRepository::belongsToUser($site, (int) $stranger['id']));
}

function test_repo_database_user_is_one_per_client(): void
{
    $db = hosting_test_db();
    $users = new UserRepository($db, new PlanRepository($db));
    $dbUsers = new DatabaseUserRepository($db);

    $user = $users->create('dbowner@example.com', 'password123', 'start');
    $first = $dbUsers->getOrCreateForUser($user, 5);
    $second = $dbUsers->getOrCreateForUser($user, 5);

    assert_equals($first['id'], $second['id'], 'Повторный вызов должен вернуть ту же запись');
    assert_equals('client1001', $first['db_user']);
}

function test_repo_job_queue_claim_and_complete(): void
{
    $db = hosting_test_db();
    $users = new UserRepository($db, new PlanRepository($db));
    $jobs = new JobRepository($db);

    $user = $users->create('jobowner@example.com', 'password123', 'start');
    $job = $jobs->enqueue('create_site', (int) $user['id'], null, ['domain' => 'shop.myhost.tj']);
    assert_equals('pending', $job['status']);

    $claimed = $jobs->claimPending(5);
    assert_equals(1, count($claimed));
    assert_equals('running', $claimed[0]['status']);

    $jobs->markSuccess((int) $claimed[0]['id']);
    $refreshed = $jobs->findById((int) $job['id']);
    assert_equals('success', $refreshed['status']);
}

function test_repo_database_belongs_to_user(): void
{
    $db = hosting_test_db();
    $users = new UserRepository($db, new PlanRepository($db));
    $databases = new DatabaseRepository($db);

    $owner = $users->create('dbowner2@example.com', 'password123', 'start');
    $stranger = $users->create('dbstranger@example.com', 'password123', 'start');
    $database = $databases->create((int) $owner['id'], null, 'client1001_shop');

    assert_true(DatabaseRepository::belongsToUser($database, (int) $owner['id']));
    assert_false(DatabaseRepository::belongsToUser($database, (int) $stranger['id']));
}
