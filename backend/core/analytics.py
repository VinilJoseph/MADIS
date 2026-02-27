"""
Token Usage and Thinking Process Analytics Module
Tracks LLM API calls, token usage, and agent execution metrics
"""
import logging
import time
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from functools import wraps
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger("core.analytics")

class TokenUsageTracker(BaseCallbackHandler):
    """
    Callback handler to track token usage and LLM calls
    """
    def __init__(self):
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.api_calls = 0
        self.call_details: List[Dict[str, Any]] = []
        
    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs) -> None:
        """Called when LLM starts running"""
        self.api_calls += 1
        logger.debug("TokenUsageTracker.on_llm_start: api_call #%d", self.api_calls)
        
    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        """Called when LLM ends running - capture token usage"""
        if response.llm_output and 'token_usage' in response.llm_output:
            usage = response.llm_output['token_usage']
            prompt_tokens = usage.get('prompt_tokens', 0)
            completion_tokens = usage.get('completion_tokens', 0)
            total = usage.get('total_tokens', 0)
            
            self.prompt_tokens += prompt_tokens
            self.completion_tokens += completion_tokens
            self.total_tokens += total
            logger.debug(
                "TokenUsageTracker.on_llm_end: prompt=%d completion=%d total=%d",
                prompt_tokens, completion_tokens, total,
            )
            
            # Store individual call details
            self.call_details.append({
                'timestamp': datetime.now().isoformat(),
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'total_tokens': total,
                'model': response.llm_output.get('model_name', 'unknown')
            })
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of token usage"""
        return {
            'total_tokens': self.total_tokens,
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'api_calls': self.api_calls,
            'call_details': self.call_details
        }
    
    def reset(self):
        """Reset all counters"""
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.api_calls = 0
        self.call_details = []


class AgentExecutionTracker:
    """
    Tracks agent execution flow, timing, and thinking process
    """
    def __init__(self):
        self.executions: List[Dict[str, Any]] = []
        self.current_execution: Optional[Dict[str, Any]] = None
        
    def start_agent(self, agent_name: str, input_data: Dict[str, Any], additional_info: Dict[str, Any] = None):
        """Start tracking an agent execution
        
        Args:
            agent_name: Name of the agent
            input_data: Input state/data passed to agent
            additional_info: Any extra metadata to log (e.g. specific parameters)
        """
        start_time = time.time()
        timestamp = datetime.now().isoformat()
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] >> Agent '{agent_name}' triggered.")
        if additional_info:
            logger.debug("AgentExecutionTracker.start_agent: context=%s", additional_info)

        self.current_execution = {
            'agent_name': agent_name,
            'start_time': start_time,
            'start_timestamp': timestamp,
            'input_size': len(str(input_data)),
            'status': 'running',
            'metadata': additional_info or {}
        }
        
    def end_agent(self, output_data: Dict[str, Any], success: bool = True, error: Optional[str] = None, additional_info: Dict[str, Any] = None):
        """End tracking an agent execution"""
        if self.current_execution:
            end_time = time.time()
            duration = end_time - self.current_execution['start_time']
            
            # Merge additional info if provided
            if additional_info:
                self.current_execution['metadata'].update(additional_info)
                
            self.current_execution.update({
                'end_time': end_time,
                'end_timestamp': datetime.now().isoformat(),
                'duration_seconds': duration,
                'output_size': len(str(output_data)),
                'success': success,
                'error': error,
                'status': 'completed' if success else 'failed'
            })
            
            status_icon = "[OK]" if success else "[FAIL]"
            logger.info(
                "AgentExecutionTracker: agent='%s' status=%s duration=%.2fs",
                self.current_execution.get('agent_name'), 'completed' if success else 'failed', duration
            )
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {status_icon} Agent completed in {duration:.2f}s.")
            
            self.executions.append(self.current_execution)
            self.current_execution = None
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """Get summary of all agent executions"""
        if not self.executions:
            return {
                'total_agents': 0,
                'total_duration': 0,
                'successful_agents': 0,
                'failed_agents': 0,
                'average_duration': 0,
                'executions': []
            }
        
        total_duration = sum(e.get('duration_seconds', 0) for e in self.executions)
        successful = sum(1 for e in self.executions if e.get('success', False))
        
        return {
            'total_agents': len(self.executions),
            'successful_agents': successful,
            'failed_agents': len(self.executions) - successful,
            'total_duration': total_duration,
            'average_duration': total_duration / len(self.executions) if self.executions else 0,
            'executions': self.executions
        }
    
    def reset(self):
        """Reset execution tracking"""
        self.executions = []
        self.current_execution = None


class AnalyticsSession:
    """
    Complete analytics session combining token usage and agent execution tracking
    """
    def __init__(self, session_id: str):
        logger.info("AnalyticsSession: new session id=%s", session_id)
        self.session_id = session_id
        self.start_time = time.time()
        self.start_timestamp = datetime.now().isoformat()
        self.token_tracker = TokenUsageTracker()
        self.agent_tracker = AgentExecutionTracker()
        self.metadata: Dict[str, Any] = {}
        
    def set_metadata(self, **kwargs):
        """Set session metadata"""
        self.metadata.update(kwargs)
    
    def get_full_report(self) -> Dict[str, Any]:
        """Get complete analytics report"""
        end_time = time.time()
        
        token_summary = self.token_tracker.get_summary()
        execution_summary = self.agent_tracker.get_execution_summary()
        
        # Calculate cost estimate (example rates - adjust based on actual model pricing)
        # Using approximate OpenRouter pricing for gemini-2.0-flash
        cost_per_1k_prompt = 0.00001  # $0.01 per 1M tokens = $0.00001 per 1k
        cost_per_1k_completion = 0.00003  # $0.03 per 1M tokens
        
        estimated_cost = (
            (token_summary['prompt_tokens'] / 1000) * cost_per_1k_prompt +
            (token_summary['completion_tokens'] / 1000) * cost_per_1k_completion
        )
        
        return {
            'session_id': self.session_id,
            'start_timestamp': self.start_timestamp,
            'end_timestamp': datetime.now().isoformat(),
            'total_duration_seconds': end_time - self.start_time,
            'metadata': self.metadata,
            'token_usage': {
                'total_tokens': token_summary['total_tokens'],
                'prompt_tokens': token_summary['prompt_tokens'],
                'completion_tokens': token_summary['completion_tokens'],
                'api_calls': token_summary['api_calls'],
                'estimated_cost_usd': round(estimated_cost, 6),
                'call_details': token_summary['call_details']
            },
            'agent_execution': {
                'total_agents': execution_summary['total_agents'],
                'successful_agents': execution_summary['successful_agents'],
                'failed_agents': execution_summary['failed_agents'],
                'total_duration': execution_summary['total_duration'],
                'average_duration': execution_summary['average_duration'],
                'executions': execution_summary['executions']
            },
            'thinking_process': self._generate_thinking_process_summary(execution_summary)
        }
    
    def _generate_thinking_process_summary(self, execution_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a summary of the AI's thinking process"""
        executions = execution_summary.get('executions', [])
        
        thinking_steps = []
        for exec_data in executions:
            thinking_steps.append({
                'step': len(thinking_steps) + 1,
                'agent': exec_data.get('agent_name'),
                'duration': exec_data.get('duration_seconds'),
                'status': exec_data.get('status'),
                'timestamp': exec_data.get('start_timestamp')
            })
        
        return {
            'total_steps': len(thinking_steps),
            'steps': thinking_steps,
            'flow': ' → '.join([s['agent'] for s in thinking_steps])
        }


def track_agent_execution(agent_name: str):
    """
    Decorator to track agent execution
    Usage: @track_agent_execution("agent_name")
    """
    def decorator(func):
        @wraps(func)
        def wrapper(state, *args, **kwargs):
            # Get tracker from state if available
            tracker = state.get('_agent_tracker')
            
            if tracker:
                tracker.start_agent(agent_name, state)
            
            try:
                result = func(state, *args, **kwargs)
                
                if tracker:
                    tracker.end_agent(result, success=True)
                
                return result
            except Exception as e:
                if tracker:
                    tracker.end_agent({}, success=False, error=str(e))
                raise
        
        return wrapper
    return decorator
