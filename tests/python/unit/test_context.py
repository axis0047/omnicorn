"""
Context Test Suite
Coverage Target: 95%
"""

import pytest

from omnicorn.orchestrator.context import Context, _decode_bytes


class TestDecodeBytes:
    """Test _decode_bytes helper function"""
    
    def test_decode_bytes_string(self):
        """Test decoding bytes to string"""
        result = _decode_bytes(b'hello')
        assert result == 'hello'
    
    def test_decode_bytes_dict(self):
        """Test decoding dict with bytes keys and values"""
        input_dict = {b'key1': b'value1', b'key2': b'value2'}
        result = _decode_bytes(input_dict)
        assert result == {'key1': 'value1', 'key2': 'value2'}
    
    def test_decode_bytes_nested_dict(self):
        """Test decoding nested dict"""
        input_dict = {
            b'outer': {
                b'inner': b'value'
            }
        }
        result = _decode_bytes(input_dict)
        assert result == {'outer': {'inner': 'value'}}
    
    def test_decode_bytes_list(self):
        """Test decoding list with bytes"""
        input_list = [b'item1', b'item2', b'item3']
        result = _decode_bytes(input_list)
        assert result == ['item1', 'item2', 'item3']
    
    def test_decode_bytes_tuple(self):
        """Test decoding tuple with bytes"""
        input_tuple = (b'item1', b'item2', b'item3')
        result = _decode_bytes(input_tuple)
        assert result == ('item1', 'item2', 'item3')
        assert isinstance(result, tuple)
    
    def test_decode_bytes_mixed(self):
        """Test decoding mixed structure"""
        input_data = {
            b'string': b'value',
            b'number': 42,
            b'list': [b'item1', 2, b'item3'],
            b'nested': {b'key': b'value'}
        }
        result = _decode_bytes(input_data)
        assert result == {
            'string': 'value',
            'number': 42,
            'list': ['item1', 2, 'item3'],
            'nested': {'key': 'value'}
        }
    
    def test_decode_bytes_already_string(self):
        """Test decoding already decoded string"""
        result = _decode_bytes('already_string')
        assert result == 'already_string'
    
    def test_decode_bytes_none(self):
        """Test decoding None"""
        result = _decode_bytes(None)
        assert result is None
    
    def test_decode_bytes_integer(self):
        """Test decoding integer"""
        result = _decode_bytes(42)
        assert result == 42
    
    def test_decode_bytes_float(self):
        """Test decoding float"""
        result = _decode_bytes(3.14)
        assert result == 3.14
    
    def test_decode_bytes_boolean(self):
        """Test decoding boolean"""
        result = _decode_bytes(True)
        assert result is True
        
        result = _decode_bytes(False)
        assert result is False


class TestContext:
    """Test Context class"""
    
    def test_context_init(self):
        """Test Context initialization"""
        ctx = Context(b'wf_123', b'step1', {b'key': b'value'})
        
        assert ctx.workflow_id == 'wf_123'
        assert ctx.step == 'step1'
        assert ctx.data == {'key': 'value'}
    
    def test_context_init_with_empty_data(self):
        """Test Context with empty data"""
        ctx = Context(b'wf_123', b'step1', None)
        
        assert ctx.data == {}
    
    def test_context_init_decodes_workflow_id(self):
        """Test Context decodes workflow_id"""
        ctx = Context(b'wf_bytes_id', b'step1', {})
        
        assert isinstance(ctx.workflow_id, str)
        assert ctx.workflow_id == 'wf_bytes_id'
    
    def test_context_init_decodes_step(self):
        """Test Context decodes step"""
        ctx = Context(b'wf_123', b'init_step', {})
        
        assert isinstance(ctx.step, str)
        assert ctx.step == 'init_step'
    
    def test_context_init_decodes_data(self):
        """Test Context decodes data"""
        data = {b'string_key': b'string_value', b'number': 42}
        ctx = Context(b'wf_123', b'step1', data)
        
        assert 'string_key' in ctx.data
        assert ctx.data['string_key'] == 'string_value'
        assert ctx.data['number'] == 42
    
    def test_context_checkpoint_basic(self):
        """Test basic checkpoint"""
        ctx = Context(b'wf_123', b'step1', {b'key': b'value'})
        
        result = ctx.checkpoint('step2')
        
        assert result[b'type'] == b'workflow_checkpoint'
        assert result[b'workflow_id'] == b'wf_123'
        assert result[b'next_step'] == b'step2'
        assert result[b'sleep_ms'] == 0
        assert result[b'data'] == {'key': 'value'}
    
    def test_context_checkpoint_with_sleep_ms(self):
        """Test checkpoint with sleep_ms"""
        ctx = Context(b'wf_123', b'step1', {})
        
        result = ctx.checkpoint('step2', sleep_ms=5000)
        
        assert result[b'sleep_ms'] == 5000
    
    def test_context_checkpoint_with_sleep_seconds(self):
        """Test checkpoint with sleep_seconds"""
        ctx = Context(b'wf_123', b'step1', {})
        
        result = ctx.checkpoint('step2', sleep_seconds=10)
        
        assert result[b'sleep_ms'] == 10000
    
    def test_context_checkpoint_with_sleep_days(self):
        """Test checkpoint with sleep_days"""
        ctx = Context(b'wf_123', b'step1', {})
        
        result = ctx.checkpoint('step2', sleep_days=1)
        
        assert result[b'sleep_ms'] == 86400000
    
    def test_context_checkpoint_combined_sleep(self):
        """Test checkpoint with combined sleep values"""
        ctx = Context(b'wf_123', b'step1', {})
        
        result = ctx.checkpoint('step2', sleep_ms=500, sleep_seconds=2, sleep_days=0)
        
        assert result[b'sleep_ms'] == 2500
    
    def test_context_checkpoint_encodes_workflow_id(self):
        """Test checkpoint encodes workflow_id to bytes"""
        ctx = Context(b'wf_123', b'step1', {})
        
        result = ctx.checkpoint('step2')
        
        assert isinstance(result[b'workflow_id'], bytes)
        assert result[b'workflow_id'] == b'wf_123'
    
    def test_context_checkpoint_encodes_next_step(self):
        """Test checkpoint encodes next_step to bytes"""
        ctx = Context(b'wf_123', b'step1', {})
        
        result = ctx.checkpoint('next_step_name')
        
        assert isinstance(result[b'next_step'], bytes)
        assert result[b'next_step'] == b'next_step_name'
    
    def test_context_checkpoint_preserves_data(self):
        """Test checkpoint preserves data"""
        ctx = Context(b'wf_123', b'step1', {b'counter': 5, b'name': b'test'})
        
        result = ctx.checkpoint('step2')
        
        assert result[b'data'] == {'counter': 5, 'name': 'test'}
    
    def test_context_finish(self):
        """Test finish method"""
        ctx = Context(b'wf_123', b'step1', {b'key': b'value'})
        
        result = ctx.finish()
        
        assert result[b'type'] == b'workflow_checkpoint'
        assert result[b'next_step'] == b'__finished__'
        assert result[b'workflow_id'] == b'wf_123'
        assert result[b'data'] == {'key': 'value'}
    
    def test_context_finish_with_data_update(self):
        """Test finish with updated data"""
        ctx = Context(b'wf_123', b'step1', {b'counter': 1})
        ctx.data['counter'] = 10
        ctx.data['finished'] = True
        
        result = ctx.finish()
        
        assert result[b'data'] == {'counter': 10, 'finished': True}
    
    def test_context_multiple_checkpoints(self):
        """Test multiple checkpoints on same context"""
        ctx = Context(b'wf_123', b'step1', {b'counter': 0})
        
        result1 = ctx.checkpoint('step2', sleep_ms=1000)
        assert result1[b'next_step'] == b'step2'
        
        ctx.step = 'step2'
        result2 = ctx.checkpoint('step3', sleep_ms=2000)
        assert result2[b'next_step'] == b'step3'
        assert result2[b'sleep_ms'] == 2000
    
    def test_context_data_modification(self):
        """Test modifying context data"""
        ctx = Context(b'wf_123', b'step1', {b'items': []})
        
        ctx.data['items'].append('item1')
        ctx.data['items'].append('item2')
        ctx.data['count'] = 2
        
        result = ctx.checkpoint('step2')
        
        assert result[b'data'] == {'items': ['item1', 'item2'], 'count': 2}
