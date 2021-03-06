"""
Copyright 2017-present, Airbnb Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
from stream_alert_cli.config import CLIConfig
from stream_alert_cli.terraform import (
    _common,
    cloudtrail,
    flow_logs,
    generate,
    streamalert
)

from mock import patch
from nose.tools import assert_equal, assert_false, assert_true


class TestTerraformGenerate(object):
    """Test class for the Terraform Cluster Generating"""
    # pylint: disable=no-self-use

    def __init__(self):
        self.cluster_dict = None
        self.config = None

    def setup(self):
        """Setup before each method"""
        self.cluster_dict = _common.infinitedict()
        self.config = CLIConfig(config_path='tests/unit/conf')

    @staticmethod
    def test_generate_s3_bucket():
        """CLI - Terraform Generate S3 Bucket """
        bucket = generate.generate_s3_bucket(
            bucket='unit.test.bucket',
            logging='my.s3-logging.bucket',
            force_destroy=True
        )

        required_keys = {
            'bucket',
            'acl',
            'force_destroy',
            'versioning',
            'logging'
        }

        assert_equal(type(bucket), dict)
        assert_equal(bucket['bucket'], 'unit.test.bucket')
        assert_equal(set(bucket.keys()), required_keys)

    @staticmethod
    def test_generate_s3_bucket_lifecycle():
        """CLI - Terraform Generate S3 Bucket with Lifecycle"""
        bucket = generate.generate_s3_bucket(
            bucket='unit.test.bucket',
            logging='my.s3-logging.bucket',
            force_destroy=False,
            lifecycle_rule={
                'prefix': 'logs/',
                'enabled': True,
                'transition': {'days': 30, 'storage_class': 'GLACIER'}
            }
        )

        assert_equal(bucket['lifecycle_rule']['prefix'], 'logs/')
        assert_equal(bucket['force_destroy'], False)
        assert_equal(type(bucket['lifecycle_rule']), dict)
        assert_equal(type(bucket['versioning']), dict)

    def test_generate_main(self):
        """CLI - Terraform Generate Main"""
        init = False

        tf_main = generate.generate_main(
            config=self.config,
            init=init
        )

        tf_main_expected = {
            'provider': {
                'aws': {
                    'version': '~> 0.1.4'
                }
            },
            'terraform': {
                'required_version': '~> 0.10.6',
                'backend': {
                    's3': {
                        'bucket': 'unit-testing.streamalert.terraform.state',
                        'key': 'stream_alert_state/terraform.tfstate',
                        'region': 'us-west-1',
                        'encrypt': True,
                        'acl': 'private',
                        'kms_key_id': 'alias/unit-testing'
                    }
                }
            },
            'resource': {
                'aws_kms_key': {
                    'stream_alert_secrets': {
                        'enable_key_rotation': True,
                        'description': 'StreamAlert secret management'
                    }
                },
                'aws_kms_alias': {
                    'stream_alert_secrets': {
                        'name': 'alias/unit-testing',
                        'target_key_id': '${aws_kms_key.stream_alert_secrets.key_id}'
                    }
                },
                'aws_s3_bucket': {
                    'lambda_source': {
                        'bucket': 'unit.testing.source.bucket',
                        'acl': 'private',
                        'force_destroy': True,
                        'versioning': {
                            'enabled': True
                        },
                        'logging': {
                            'target_bucket': 'unit-testing.streamalert.s3-logging',
                            'target_prefix': 'unit.testing.source.bucket/'
                        }
                    },
                    'stream_alert_secrets': {
                        'bucket': 'unit-testing.streamalert.secrets',
                        'acl': 'private',
                        'force_destroy': True,
                        'versioning': {
                            'enabled': True
                        },
                        'logging': {
                            'target_bucket': 'unit-testing.streamalert.s3-logging',
                            'target_prefix': 'unit-testing.streamalert.secrets/'
                        }
                    },
                    'terraform_remote_state': {
                        'bucket': 'unit-testing.terraform.tfstate',
                        'acl': 'private',
                        'force_destroy': True,
                        'versioning': {
                            'enabled': True
                        },
                        'logging': {
                            'target_bucket': 'unit-testing.streamalert.s3-logging',
                            'target_prefix': 'unit-testing.terraform.tfstate/'
                        }
                    },
                    'logging_bucket': {
                        'bucket': 'unit-testing.streamalert.s3-logging',
                        'acl': 'log-delivery-write',
                        'force_destroy': True,
                        'versioning': {
                            'enabled': True
                        },
                        'logging': {
                            'target_bucket': 'unit-testing.streamalert.s3-logging',
                            'target_prefix': 'unit-testing.streamalert.s3-logging/'
                        },
                        'lifecycle_rule': {
                            'prefix': '/',
                            'enabled': True,
                            'transition': {
                                'days': 30,
                                'storage_class': 'GLACIER'
                            }
                        }
                    },
                    'streamalerts': {
                        'bucket': 'unit-testing.streamalerts',
                        'acl': 'private',
                        'force_destroy': True,
                        'versioning': {
                            'enabled': True
                        },
                        'logging': {
                            'target_bucket': 'unit-testing.streamalert.s3-logging',
                            'target_prefix': 'unit-testing.streamalerts/'
                        }
                    }
                },
                'aws_sns_topic': {
                    'stream_alert_monitoring': {
                        'name': 'stream_alert_monitoring'
                    }
                }
            }
        }

        assert_equal(tf_main['provider'], tf_main_expected['provider'])
        assert_equal(tf_main['terraform'], tf_main_expected['terraform'])
        assert_equal(tf_main['resource'], tf_main_expected['resource'])

    def test_generate_main_with_firehose(self):
        """CLI - Terraform Generate Main with Firehose Enabled"""
        self.config['global']['infrastructure']['firehose'] = {
            'enabled': True,
            's3_bucket_suffix': 'my-data',
            'buffer_size': 10,
            'buffer_interval': 650
        }
        tf_main = generate.generate_main(
            config=self.config,
            init=False
        )

        generated_firehose = tf_main['module']['kinesis_firehose']

        assert_equal(generated_firehose['s3_bucket_name'], 'unit-testing.my-data')
        assert_equal(generated_firehose['buffer_size'], 10)
        assert_equal(generated_firehose['buffer_interval'], 650)

    def test_generate_stream_alert_test(self):
        """CLI - Terraform Generate StreamAlert - Test Cluster"""
        streamalert.generate_stream_alert(
            'test',
            self.cluster_dict,
            self.config
        )

        expected_test_cluster = {
            'module': {
                'stream_alert_test': {
                    'source': 'modules/tf_stream_alert',
                    'account_id': '12345678910',
                    'region': 'us-west-1',
                    'prefix': 'unit-testing',
                    'cluster': 'test',
                    'kms_key_arn': '${aws_kms_key.stream_alert_secrets.arn}',
                    'rule_processor_enable_metrics': True,
                    'rule_processor_log_level': 'info',
                    'rule_processor_memory': 128,
                    'rule_processor_timeout': 25,
                    'rule_processor_version': '$LATEST',
                    'rule_processor_config': '${var.rule_processor_config}',
                    'alert_processor_enable_metrics': True,
                    'alert_processor_log_level': 'info',
                    'alert_processor_memory': 128,
                    'alert_processor_timeout': 25,
                    'alert_processor_version': '$LATEST',
                    'alert_processor_config': '${var.alert_processor_config}',
                }
            }
        }

        assert_equal(self.cluster_dict['module']['stream_alert_test'],
                     expected_test_cluster['module']['stream_alert_test'])

    def test_generate_stream_alert_advanced(self):
        """CLI - Terraform Generate StreamAlert - Advanced Cluster"""
        streamalert.generate_stream_alert(
            'advanced',
            self.cluster_dict,
            self.config
        )

        expected_advanced_cluster = {
            'module': {
                'stream_alert_advanced': {
                    'source': 'modules/tf_stream_alert',
                    'account_id': '12345678910',
                    'region': 'us-west-1',
                    'prefix': 'unit-testing',
                    'cluster': 'advanced',
                    'kms_key_arn': '${aws_kms_key.stream_alert_secrets.arn}',
                    'rule_processor_enable_metrics': True,
                    'rule_processor_log_level': 'info',
                    'rule_processor_memory': 128,
                    'rule_processor_timeout': 25,
                    'rule_processor_version': '$LATEST',
                    'rule_processor_config': '${var.rule_processor_config}',
                    'alert_processor_enable_metrics': True,
                    'alert_processor_log_level': 'info',
                    'alert_processor_memory': 128,
                    'alert_processor_timeout': 25,
                    'alert_processor_version': '$LATEST',
                    'alert_processor_config': '${var.alert_processor_config}',
                    'output_lambda_functions': ['my-lambda-function:production'],
                    'output_s3_buckets': ['my-s3-bucket.with.data'],
                    'input_sns_topics': ['my-sns-topic-name'],
                    'alert_processor_vpc_enabled': True,
                    'alert_processor_vpc_subnet_ids': ['subnet-id-1'],
                    'alert_processor_vpc_security_group_ids': ['sg-id-1']
                }
            }
        }

        assert_equal(self.cluster_dict['module']['stream_alert_advanced'],
                     expected_advanced_cluster['module']['stream_alert_advanced'])

    def test_generate_flow_logs(self):
        """CLI - Terraform Generate Flow Logs"""
        cluster_name = 'advanced'
        flow_logs.generate_flow_logs(
            cluster_name,
            self.cluster_dict,
            self.config
        )

        flow_log_config = self.cluster_dict['module']['flow_logs_advanced']
        assert_equal(flow_log_config['flow_log_group_name'], 'unit-test-advanced')
        assert_equal(flow_log_config['vpcs'], ['vpc-id-1', 'vpc-id-2'])

    def test_generate_cloudtrail_basic(self):
        """CLI - Terraform Generate Cloudtrail Module - Legacy"""
        cluster_name = 'advanced'
        self.config['clusters']['advanced']['modules']['cloudtrail'] = {
            'enabled': True
        }
        result = cloudtrail.generate_cloudtrail(cluster_name, self.cluster_dict, self.config)
        # Reload the config
        self.config.load()

        assert_true(result)
        assert_equal(set(self.config['clusters']['advanced']['modules']['cloudtrail'].keys()),
                     {'enable_logging', 'enable_kinesis'})
        assert_equal(self.cluster_dict['module']['cloudtrail_advanced'], {
            'account_ids': ['12345678910'],
            'cluster': 'advanced',
            'kinesis_arn': '${module.kinesis_advanced.arn}',
            'prefix': 'unit-testing',
            'enable_logging': True,
            'enable_kinesis': True,
            'source': 'modules/tf_stream_alert_cloudtrail',
            's3_logging_bucket': 'unit-testing.streamalert.s3-logging',
            'existing_trail': False,
            'is_global_trail': True,
            'event_pattern': '{"account": ["12345678910"]}'
        })

    def test_generate_cloudtrail_all_options(self):
        """CLI - Terraform Generate Cloudtrail Module - All Options"""
        cluster_name = 'advanced'
        self.config['clusters']['advanced']['modules']['cloudtrail'] = {
            'enable_logging': True,
            'enable_kinesis': True,
            'existing_trail': False,
            'is_global_trail': False,
            'event_pattern': {
                'source': ['aws.ec2'],
                'account': '12345678910',
                'detail': {
                    'state': ['running']
                }
            }
        }
        cloudtrail.generate_cloudtrail(
            cluster_name,
            self.cluster_dict,
            self.config
        )

        assert_equal('cloudtrail_advanced' in self.cluster_dict['module'], True)
        assert_equal(self.cluster_dict['module']['cloudtrail_advanced'], {
            'account_ids': ['12345678910'],
            'cluster': 'advanced',
            'existing_trail': False,
            'is_global_trail': False,
            'kinesis_arn': '${module.kinesis_advanced.arn}',
            'prefix': 'unit-testing',
            'enable_logging': True,
            'enable_kinesis': True,
            'source': 'modules/tf_stream_alert_cloudtrail',
            's3_logging_bucket': 'unit-testing.streamalert.s3-logging',
            'event_pattern': '{"source": ["aws.ec2"], "account": "12345678910",'
                             ' "detail": {"state": ["running"]}}'
        })

    @patch('stream_alert_cli.terraform.cloudtrail.LOGGER_CLI')
    def test_generate_cloudtrail_invalid_event_pattern(self, mock_logging):
        """CLI - Terraform Generate Cloudtrail Module - Invalid Event Pattern"""
        cluster_name = 'advanced'
        self.config['clusters']['advanced']['modules']['cloudtrail'] = {
            'enable_logging': True,
            'enable_kinesis': True,
            'existing_trail': False,
            'is_global_trail': False,
            'event_pattern': {
                'invalid': ['aws.ec2']
            }
        }
        result = cloudtrail.generate_cloudtrail(cluster_name, self.cluster_dict, self.config)
        assert_false(result)
        assert_true(mock_logging.error.called)

    def test_generate_cluster_test(self):
        """CLI - Terraform Generate Test Cluster"""

        tf_cluster = generate.generate_cluster(
            config=self.config,
            cluster_name='test'
        )

        cluster_keys = {'module', 'output'}

        test_modules = {
            'stream_alert_test',
            'cloudwatch_monitoring_test',
            'kinesis_test',
            'kinesis_events_test',
            's3_events_unit-testing_test_0'
        }

        assert_equal(set(tf_cluster['module'].keys()), test_modules)
        assert_equal(set(tf_cluster.keys()), cluster_keys)

    def test_generate_cluster_advanced(self):
        """CLI - Terraform Generate Advanced Cluster"""

        tf_cluster = generate.generate_cluster(
            config=self.config,
            cluster_name='advanced'
        )

        cluster_keys = {
            'module',
            'output'
        }

        advanced_modules = {
            'stream_alert_advanced',
            'cloudwatch_monitoring_advanced',
            'kinesis_advanced',
            'kinesis_events_advanced',
            'flow_logs_advanced',
            'cloudtrail_advanced',
            's3_events_unit-testing_advanced_1',
            's3_events_unit-testing_advanced_0'
        }

        assert_equal(set(tf_cluster['module'].keys()), advanced_modules)
        assert_equal(set(tf_cluster.keys()), cluster_keys)
