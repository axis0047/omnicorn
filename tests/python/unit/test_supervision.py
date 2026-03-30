"""
Supervision and Config Test Suite
Coverage Target: 90%
"""

import pytest
from unittest.mock import patch, MagicMock
import os
import sys

from omnicorn.supervision import let_it_crash
from omnicorn.config import ConfigLoader
from omnicorn.config.yaml_adapter import load_yaml
from omnicorn.config.gunicorn_adapter import load_gunicorn
from omnicorn.config.uwsgi_adapter import load_uwsgi


class TestLetItCrash:
    """Test let_it_crash decorator"""
    
    def test_let_it_crash_success(self):
        """Test decorated function that succeeds"""
        @let_it_crash()
        def success_func():
            return "success"
        
        result = success_func()
        assert result == "success"
    
    def test_let_it_crash_catches_exception(self):
        """Test decorated function that raises exception"""
        @let_it_crash(log=False)
        def fail_func():
            raise ValueError("Test error")
        
        with pytest.raises(SystemExit):
            fail_func()
    
    def test_let_it_crash_custom_exceptions(self):
        """Test decorator with custom exception types"""
        @let_it_crash(exceptions=(ValueError,), log=False)
        def fail_func():
            raise ValueError("Test error")
        
        with pytest.raises(SystemExit):
            fail_func()
    
    def test_let_it_crash_ignored_exception(self):
        """Test decorator ignores non-specified exceptions"""
        @let_it_crash(exceptions=(ValueError,), log=False)
        def fail_func():
            raise TypeError("Different error")
        
        with pytest.raises(TypeError):
            fail_func()
    
    def test_let_it_crash_with_logging(self, capsys):
        """Test decorator logs error"""
        @let_it_crash(log=True)
        def fail_func():
            raise ValueError("Test error")
        
        with pytest.raises(SystemExit):
            fail_func()
        
        captured = capsys.readouterr()
        assert "fatal error" in captured.err
    
    def test_let_it_crash_preserves_function_name(self):
        """Test decorator preserves function metadata"""
        @let_it_crash()
        def named_func():
            pass
        
        assert named_func.__name__ == "named_func"


class TestConfigLoader:
    """Test ConfigLoader class"""
    
    def test_load_default_config(self):
        """Test loading default config"""
        config = ConfigLoader.load(None)
        
        assert config['server']['port'] == 8080
        assert config['workers']['count'] > 0  # Based on CPU count
        assert config['upstream']['app_path'] == 'main:app'
        assert config['upstream']['mode'] == 'auto'
    
    def test_load_yaml_config(self, tmp_path):
        """Test loading YAML config"""
        config_file = tmp_path / "test.yaml"
        config_file.write_text("""
server:
  port: 9000
workers:
  count: 2
upstream:
  app_path: "myapp:app"
""")
        
        config = ConfigLoader.load(str(config_file))
        
        assert config['server']['port'] == 9000
        assert config['workers']['count'] == 2
        assert config['upstream']['app_path'] == 'myapp:app'
    
    def test_load_gunicorn_config(self, tmp_path):
        """Test loading Gunicorn config"""
        config_file = tmp_path / "gunicorn.conf.py"
        config_file.write_text("""
workers = 4
bind = "127.0.0.1:8000"
timeout = 30
""")
        
        config = ConfigLoader.load(str(config_file))
        
        assert config['workers']['count'] == 4
        assert config['server']['port'] == 8000
        assert config['workers']['timeout'] == 30000
    
    def test_load_uwsgi_config(self, tmp_path):
        """Test loading uWSGI config"""
        config_file = tmp_path / "uwsgi.ini"
        config_file.write_text("""
[uwsgi]
processes = 8
module = myapp:app
http = :7000
""")
        
        config = ConfigLoader.load(str(config_file))
        
        assert config['workers']['count'] == 8
        assert config['upstream']['app_path'] == 'myapp:app'
        assert config['server']['port'] == 7000
    
    def test_load_nonexistent_file(self):
        """Test loading nonexistent config file"""
        config = ConfigLoader.load("/nonexistent/config.yaml")
        
        # Should return defaults
        assert config['server']['port'] == 8080
    
    def test_load_sets_worker_count_from_cpu(self):
        """Test worker count is set from CPU count if 0"""
        with patch('multiprocessing.cpu_count', return_value=4):
            config = ConfigLoader.load(None)
            
            # Should be (4 * 2) + 1 = 9
            assert config['workers']['count'] == 9


class TestYamlAdapter:
    """Test YAML adapter"""
    
    def test_load_yaml_basic(self, tmp_path):
        """Test basic YAML loading"""
        config_file = tmp_path / "test.yaml"
        config_file.write_text("""
server:
  port: 8080
workers:
  count: 4
""")
        
        config = {'server': {'port': 80}, 'workers': {'count': 1}}
        result = load_yaml(str(config_file), config)
        
        assert result['server']['port'] == 8080
        assert result['workers']['count'] == 4
    
    def test_load_yaml_partial_update(self, tmp_path):
        """Test YAML partial update"""
        config_file = tmp_path / "test.yaml"
        config_file.write_text("""
server:
  port: 9000
""")
        
        config = {
            'server': {'port': 80, 'socket': 'localhost:80'},
            'workers': {'count': 4}
        }
        result = load_yaml(str(config_file), config)
        
        assert result['server']['port'] == 9000
        assert result['server']['socket'] == 'localhost:80'
        assert result['workers']['count'] == 4


class TestGunicornAdapter:
    """Test Gunicorn adapter"""
    
    def test_load_gunicorn_basic(self, tmp_path):
        """Test basic Gunicorn config loading"""
        config_file = tmp_path / "gunicorn.conf.py"
        config_file.write_text("""
workers = 4
bind = "127.0.0.1:8000"
timeout = 30
""")
        
        config = {}
        result = load_gunicorn(str(config_file), config)
        
        assert result['workers']['count'] == 4
        assert result['server']['port'] == 8000
        assert result['workers']['timeout'] == 30000
    
    def test_load_gunicorn_invalid_file(self, tmp_path):
        """Test Gunicorn config with invalid file"""
        config_file = tmp_path / "invalid.py"
        config_file.write_text("invalid python syntax ==")
        
        config = {'workers': {'count': 4}}
        result = load_gunicorn(str(config_file), config)
        
        # Should return original config
        assert result['workers']['count'] == 4


class TestUwsgiAdapter:
    """Test uWSGI adapter"""
    
    def test_load_uwsgi_basic(self, tmp_path):
        """Test basic uWSGI config loading"""
        config_file = tmp_path / "uwsgi.ini"
        config_file.write_text("""
[uwsgi]
processes = 8
module = myapp:app
http = :7000
""")
        
        config = {}
        result = load_uwsgi(str(config_file), config)
        
        assert result['workers']['count'] == 8
        assert result['upstream']['app_path'] == 'myapp:app'
        assert result['server']['port'] == 7000
    
    def test_load_uwsgi_empty_section(self, tmp_path):
        """Test uWSGI config with empty section"""
        config_file = tmp_path / "uwsgi.ini"
        config_file.write_text("""
[other]
key = value
""")
        
        config = {'workers': {'count': 4}}
        result = load_uwsgi(str(config_file), config)
        
        # Should return original config
        assert result['workers']['count'] == 4
