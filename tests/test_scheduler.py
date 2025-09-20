from app.scheduler.tasks import SchedulerService


def test_scheduler_service_has_required_methods():
    service = SchedulerService()

    required_methods = [
        'check_urgent_tasks',
        'release_expired_holds',
        'finalize_ended_auctions',
        'send_notifications',
        'cleanup_tasks',
        'daily_tasks',
        '_add_scheduled_jobs',
        '_check_ending_auctions_soon',
        '_check_dispute_windows_closing',
        '_finalize_auction',
        '_send_price_drop_notifications',
        '_send_expiry_notifications',
        '_send_favorite_notifications',
        '_cleanup_expired_coupons',
        '_update_seller_daily_quotas',
        '_generate_daily_reports',
        '_send_telegram_notification',
        '_send_admin_notification',
        '_is_seller_verified',
        '_notify_auction_ending_soon',
        '_send_dispute_window_reminder',
        '_notify_seller_payment_released',
        '_notify_auction_winner',
        '_notify_auction_losers',
        '_cleanup_old_transactions',
        '_cleanup_old_data',
        '_backup_important_data',
    ]

    for name in required_methods:
        assert hasattr(service, name), f"SchedulerService missing method: {name}"