from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from jellyport import notifications
from jellyport.core import Store, Worker, defaults, new_job, public_settings

HOOK = 'https://ntfy.example/secret-topic'


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = defaults()
        self.config['downloader'].update(url='http://downloader.local:8080', local_root=str(self.root/'dl'), remote_root='/downloads')
        self.config['library'] = {'movies': str(self.root/'m'), 'tv': str(self.root/'t')}
        for path in (self.root/'dl', self.root/'m', self.root/'t'):
            path.mkdir()
        self.store = Store(self.root/'state')
        self.store.save_settings(self.config)
        self.worker = Worker(self.store)
        self.job = new_job(self.store.settings(), {'title': 'Film', 'year': '2020', 'link': 'magnet:?xt=urn:btih:' + 'a'*40})
        self.store.save_job(self.job)

    def tearDown(self):
        self.temp.cleanup()

    def set_hook(self, url=HOOK):
        self.store.save_settings({'notifications': {'webhook_url': url}})

    def test_webhook_is_a_secret_that_survives_other_saves_and_can_be_cleared(self):
        self.set_hook()
        public = self.store.save_settings({'preferences': {'quality': '1080'}})
        self.assertTrue(public['notifications']['webhook_url_set'])
        self.assertNotIn('webhook_url', public['notifications'])
        self.assertNotIn('secret-topic', str(public_settings(self.store.settings())))
        self.assertEqual(self.store.settings()['notifications']['webhook_url'], HOOK)
        self.store.save_settings({'notifications': {'clear': 'on'}})
        self.assertEqual(self.store.settings()['notifications']['webhook_url'], '')
        for bad in ('ftp://x/y', 'https://user:pw@host/x', 5):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.store.save_settings({'notifications': {'webhook_url': bad}})

    def test_legacy_settings_get_defaults_without_rewrite(self):
        with self.store.connect() as db:
            import json
            body = json.loads(db.execute('SELECT body FROM settings WHERE id=1').fetchone()[0])
            body.pop('notifications')
            db.execute('UPDATE settings SET body=? WHERE id=1', (json.dumps(body),))
        self.assertEqual(self.store.settings()['notifications'], {'webhook_url': ''})

    def test_import_and_each_distinct_error_notify_once(self):
        self.set_hook()
        job = self.store.job(self.job['id'])
        with patch('jellyport.core.notifications.send') as send:
            job.update(state='done', files_imported=['Film (2020)/Film (2020).mkv'])
            self.worker.notify(job)
            self.worker.notify(job)
            self.assertEqual(send.call_count, 1)
            self.assertIn('geïmporteerd', send.call_args.args[1])
            job.update(state='error', error='Schijf vol')
            self.worker.notify(job)
            self.worker.notify(job)
            job.update(error='Andere fout')
            self.worker.notify(job)
            self.assertEqual(send.call_count, 3)

    def test_failed_delivery_never_breaks_the_task_or_repeats(self):
        self.set_hook()
        job = self.store.job(self.job['id'])
        job.update(state='done', files_imported=['x.mkv'])
        with patch('jellyport.core.notifications.send', side_effect=ValueError('boom')) as send:
            self.worker.notify(job)
            self.worker.notify(job)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(self.store.job(job['id'])['state'], 'done')

    def test_no_webhook_means_no_request_and_no_backfill(self):
        job = self.store.job(self.job['id'])
        job.update(state='done', files_imported=['x.mkv'])
        with patch('jellyport.core.notifications.send') as send:
            self.worker.notify(job)
            self.set_hook()
            self.worker.notify(job)
        send.assert_not_called()

    def test_payload_formats(self):
        body, headers = notifications.payload('https://discord.com/api/webhooks/1/x', 'T', 'M')
        self.assertIn(b'"content"', body)
        body, headers = notifications.payload('https://hooks.slack.com/services/x', 'T', 'M')
        self.assertIn(b'"text"', body)
        body, headers = notifications.payload(HOOK, 'T', 'M')
        self.assertEqual(body, 'T: M'.encode())
        with patch('jellyport.notifications.request') as request:
            notifications.send(HOOK, 'T', 'M')
        self.assertEqual(request.call_args.args[0], HOOK)


if __name__ == '__main__':
    unittest.main()
