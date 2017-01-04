import json
import os
import time
from zipfile import ZIP_DEFLATED, ZipFile

import requests
from logger import logger

from perfrunner.helpers.misc import pretty_dict, uhex
from perfrunner.settings import StatsSettings


class SFReporter(object):

    def __init__(self, test):
        self.test = test

    def _post_cluster(self):
        cluster = self.test.cluster_spec.parameters
        cluster['Name'] = self.test.cluster_spec.name

        logger.info('Adding a cluster: {}'.format(pretty_dict(cluster)))
        requests.post('http://{}/api/v1/clusters'.format(StatsSettings.SHOWFAST),
                      json.dumps(cluster))

    def _post_metric(self, metric, metric_info):
        if metric_info is None:
            metric_info = {'title': self.test.test_config.test_case.title}
        metric_info['id'] = metric
        metric_info['cluster'] = self.test.cluster_spec.name
        metric_info['component'] = self.test.test_config.test_case.component
        metric_info['category'] = \
            metric_info.get('category', self.test.test_config.test_case.category)
        metric_info['subCategory'] = self.test.test_config.test_case.sub_category

        logger.info('Adding a metric: {}'.format(pretty_dict(metric_info)))
        requests.post('http://{}/api/v1/metrics'.format(StatsSettings.SHOWFAST),
                      json.dumps(metric_info))

    def _generate_benchmark(self, metric, value):
        return {
            'build': self.test.build,
            'buildURL': os.environ.get('BUILD_URL'),
            'dateTime': time.strftime('%Y-%m-%d %H:%M'),
            'id': uhex(),
            'metric': metric,
            'snapshots': self.test.snapshots,
            'value': value,
        }

    def _log_benchmark(self, metric, value):
        benchmark = self._generate_benchmark(metric, value)

        logger.info('Dry run stats: {}'.format(pretty_dict(benchmark)))

    def _post_benchmark(self, metric, value):
        benchmark = self._generate_benchmark(metric, value)

        logger.info('Adding a benchmark: {}'.format(pretty_dict(benchmark)))
        requests.post('http://{}/api/v1/benchmarks'.format(StatsSettings.SHOWFAST),
                      json.dumps(benchmark))

    def post_to_sf(self, value, metric=None, metric_info=None):
        if metric is None:
            metric = self.test.test_config.name
        metric = '{}_{}'.format(metric, self.test.cluster_spec.name)

        if self.test.test_config.stats_settings.post_to_sf:
            self._post_benchmark(metric, value)
            self._post_metric(metric, metric_info)
            self._post_cluster()
        else:
            self._log_benchmark(metric, value)


class DailyReporter(object):

    def __init__(self, test):
        self.test = test

    def _post(self, benchmark):
        logger.info('Adding a benchmark: {}'.format(pretty_dict(benchmark)))
        requests.post(
            'http://{}/daily/api/v1/benchmarks'.format(StatsSettings.SHOWFAST),
            json.dumps(benchmark))

    def post_to_daily(self, metric, value):
        benchmark = {
            'build': self.test.build,
            'buildURL': os.environ.get('BUILD_URL', ''),
            'component': self.test.test_config.test_case.component,
            'dateTime': time.strftime('%Y-%m-%d %H:%M'),
            'greaterIsBetter': self.test.test_config.test_case.greater_is_better,
            'metric': metric,
            'snapshots': self.test.snapshots,
            'threshold': self.test.test_config.test_case.threshold,
            'title': self.test.test_config.test_case.title,
            'value': value,
        }
        self._post(benchmark)


class LogReporter(object):

    def __init__(self, test):
        self.test = test

    def save_master_events(self):
        with ZipFile('master_events.zip', 'w', ZIP_DEFLATED) as zh:
            for master in self.test.cluster_spec.yield_masters():
                master_events = self.test.rest.get_master_events(master)
                self.test.master_events.append(master_events)
                fname = 'master_events_{}.log'.format(master.split(':')[0])
                zh.writestr(zinfo_or_arcname=fname, bytes=master_events)


class Reporter(SFReporter, LogReporter, DailyReporter):

    def start(self):
        self.ts = time.time()

    def finish(self, action, time_elapsed=None):
        time_elapsed = time_elapsed or (time.time() - self.ts)
        time_elapsed = round(time_elapsed / 60, 2)
        logger.info(
            'Time taken to perform "{}": {} min'.format(action, time_elapsed)
        )
        return time_elapsed
