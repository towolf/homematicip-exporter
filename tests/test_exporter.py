import unittest
from unittest.mock import MagicMock, patch
import sys
import argparse
import asyncio
import logging

# Mock the homematicip module before importing exporter
sys.modules['homematicip'] = MagicMock()
sys.modules['homematicip.home'] = MagicMock()
sys.modules['homematicip.device'] = MagicMock()
sys.modules['homematicip.base.functionalChannels'] = MagicMock()

# Now import the exporter
from exporter import HomematicIPCollector

class TestHomematicIPCollector(unittest.TestCase):
    def setUp(self):
        # Setup basic args
        self.args = argparse.Namespace(
            metric_port=8000,
            config_file='dummy_config.ini',
            auth_token='dummy_token',
            access_point='dummy_ap',
            log_level=20
        )
        
        # Setup the mock Home client
        self.mock_home_cls = sys.modules['homematicip.home'].Home
        self.mock_home_instance = self.mock_home_cls.return_value
        self.mock_home_instance.groups = [] # Empty groups for simplicity
        
        # Mock the config object return
        sys.modules['homematicip'].HmipConfig.return_value = MagicMock(
            auth_token='dummy_token',
            access_point='dummy_ap'
        )

    def test_collect_event_loop_handling(self):
        """
        Test that collect() successfully creates/uses an event loop and calls get_current_state
        without raising RuntimeError.
        """
        collector = HomematicIPCollector(self.args)
        
        # Execute the generator
        # We wrap this in a way that simulates how prometheus_client calls it (often from a thread)
        # But for this unit test, just iterating over it is enough to trigger the code.
        
        try:
            # Consume the generator
            list(collector.collect())
        except RuntimeError as e:
            self.fail(f"collect() raised RuntimeError: {e}")
        except Exception as e:
            # We expect it might fail on other things due to heavy mocking, 
            # but we specifically want to ensure it passed the event loop check
            # and tried to call get_current_state
            print(f"Caught expected side-effect exception from mocks: {e}")

        # Verify get_current_state was called
        self.mock_home_instance.get_current_state.assert_called_once()
        
        # Verify an event loop is present (we can't easily check 'during' the call 
        # without more complex mocking, but success implies the loop logic worked)
        try:
            loop = asyncio.get_event_loop()
            self.assertTrue(loop is not None)
        except RuntimeError:
            self.fail("No event loop available after collect()")

if __name__ == '__main__':
    logging.disable(logging.CRITICAL) # Silence logs during test
    unittest.main()
