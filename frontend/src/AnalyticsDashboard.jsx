import React, { useState, useEffect } from 'react';
import { 
   BarChart3, 
   Clock, 
   DollarSign, 
   Activity, 
   TrendingUp, 
   Zap,
   CheckCircle,
   XCircle,
   Brain,
   ArrowRight
} from 'lucide-react';

function AnalyticsDashboard({ analytics }) {
   if (!analytics) return null;

   const tokenUsage = analytics.token_usage || {};
   const agentExecution = analytics.agent_execution || {};
   const thinkingProcess = analytics.thinking_process || {};

   return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', marginTop: '24px' }}>
         
         {/* Header */}
         <div className="card" style={{ padding: '24px', background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', color: 'white' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
               <Activity size={24} />
               <h2 style={{ fontSize: '20px', fontWeight: '600', margin: 0 }}>
                  Analytics Dashboard
               </h2>
            </div>
            <p style={{ margin: 0, opacity: 0.9, fontSize: '14px' }}>
               Session ID: {analytics.session_id?.substring(0, 8)}...
            </p>
         </div>

         {/* Key Metrics Grid */}
         <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
            
            {/* Total Tokens */}
            <div className="card metric-card" style={{ padding: '20px' }}>
               <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                  <div style={{ 
                     width: '40px', 
                     height: '40px', 
                     borderRadius: '10px', 
                     background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                     display: 'flex',
                     alignItems: 'center',
                     justifyContent: 'center'
                  }}>
                     <BarChart3 size={20} color="white" />
                  </div>
               </div>
               <div style={{ fontSize: '28px', fontWeight: '700', marginBottom: '4px', color: 'var(--text-main)' }}>
                  {tokenUsage.total_tokens?.toLocaleString() || 0}
               </div>
               <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                  Total Tokens
               </div>
               <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '8px' }}>
                  Prompt: {tokenUsage.prompt_tokens?.toLocaleString() || 0} | 
                  Completion: {tokenUsage.completion_tokens?.toLocaleString() || 0}
               </div>
            </div>

            {/* API Calls */}
            <div className="card metric-card" style={{ padding: '20px' }}>
               <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                  <div style={{ 
                     width: '40px', 
                     height: '40px', 
                     borderRadius: '10px', 
                     background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
                     display: 'flex',
                     alignItems: 'center',
                     justifyContent: 'center'
                  }}>
                     <Zap size={20} color="white" />
                  </div>
               </div>
               <div style={{ fontSize: '28px', fontWeight: '700', marginBottom: '4px', color: 'var(--text-main)' }}>
                  {tokenUsage.api_calls || 0}
               </div>
               <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                  API Calls
               </div>
            </div>

            {/* Estimated Cost */}
            <div className="card metric-card" style={{ padding: '20px' }}>
               <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                  <div style={{ 
                     width: '40px', 
                     height: '40px', 
                     borderRadius: '10px', 
                     background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
                     display: 'flex',
                     alignItems: 'center',
                     justifyContent: 'center'
                  }}>
                     <DollarSign size={20} color="white" />
                  </div>
               </div>
               <div style={{ fontSize: '28px', fontWeight: '700', marginBottom: '4px', color: 'var(--text-main)' }}>
                  ${tokenUsage.estimated_cost_usd?.toFixed(6) || '0.000000'}
               </div>
               <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                  Estimated Cost
               </div>
            </div>

            {/* Processing Time */}
            <div className="card metric-card" style={{ padding: '20px' }}>
               <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                  <div style={{ 
                     width: '40px', 
                     height: '40px', 
                     borderRadius: '10px', 
                     background: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
                     display: 'flex',
                     alignItems: 'center',
                     justifyContent: 'center'
                  }}>
                     <Clock size={20} color="white" />
                  </div>
               </div>
               <div style={{ fontSize: '28px', fontWeight: '700', marginBottom: '4px', color: 'var(--text-main)' }}>
                  {analytics.total_duration_seconds?.toFixed(2) || 0}s
               </div>
               <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                  Processing Time
               </div>
            </div>

         </div>

         {/* Agent Execution Summary */}
         <div className="card" style={{ padding: '24px' }}>
            <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
               <Brain size={18} />
               Agent Execution Summary
            </h3>
            
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '16px', marginBottom: '20px' }}>
               <div style={{ textAlign: 'center', padding: '16px', background: 'var(--bg)', borderRadius: '8px' }}>
                  <div style={{ fontSize: '24px', fontWeight: '700', color: '#10b981', marginBottom: '4px' }}>
                     {agentExecution.successful_agents || 0}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}>
                     <CheckCircle size={14} color="#10b981" />
                     Successful
                  </div>
               </div>
               
               <div style={{ textAlign: 'center', padding: '16px', background: 'var(--bg)', borderRadius: '8px' }}>
                  <div style={{ fontSize: '24px', fontWeight: '700', color: '#ef4444', marginBottom: '4px' }}>
                     {agentExecution.failed_agents || 0}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}>
                     <XCircle size={14} color="#ef4444" />
                     Failed
                  </div>
               </div>
               
               <div style={{ textAlign: 'center', padding: '16px', background: 'var(--bg)', borderRadius: '8px' }}>
                  <div style={{ fontSize: '24px', fontWeight: '700', color: '#2563eb', marginBottom: '4px' }}>
                     {agentExecution.average_duration?.toFixed(2) || 0}s
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                     Avg Duration
                  </div>
               </div>
            </div>

            {/* Agent Execution Timeline */}
            {agentExecution.executions && agentExecution.executions.length > 0 && (
               <div>
                  <h4 style={{ fontSize: '14px', fontWeight: '600', marginBottom: '12px', color: 'var(--text-muted)' }}>
                     Execution Timeline
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                     {agentExecution.executions.map((exec, idx) => (
                        <div 
                           key={idx} 
                           style={{ 
                              padding: '12px 16px',
                              background: exec.success ? '#f0fdf4' : '#fef2f2',
                              border: `1px solid ${exec.success ? '#bbf7d0' : '#fecaca'}`,
                              borderRadius: '6px',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between'
                           }}
                        >
                           <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                              <div style={{ 
                                 width: '24px', 
                                 height: '24px', 
                                 borderRadius: '50%',
                                 background: exec.success ? '#10b981' : '#ef4444',
                                 color: 'white',
                                 display: 'flex',
                                 alignItems: 'center',
                                 justifyContent: 'center',
                                 fontSize: '11px',
                                 fontWeight: '600'
                              }}>
                                 {idx + 1}
                              </div>
                              <div>
                                 <div style={{ fontSize: '14px', fontWeight: '500', marginBottom: '2px' }}>
                                    {exec.agent_name}
                                 </div>
                                 <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                                    {exec.status}
                                 </div>
                              </div>
                           </div>
                           <div style={{ fontSize: '13px', fontWeight: '600', color: exec.success ? '#10b981' : '#ef4444' }}>
                              {exec.duration_seconds?.toFixed(3)}s
                           </div>
                        </div>
                     ))}
                  </div>
               </div>
            )}
         </div>

         {/* Thinking Process Flow */}
         {thinkingProcess.steps && thinkingProcess.steps.length > 0 && (
            <div className="card" style={{ padding: '24px' }}>
               <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <TrendingUp size={18} />
                  Thinking Process Flow
               </h3>
               
               <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '8px', 
                  flexWrap: 'wrap',
                  padding: '16px',
                  background: 'var(--bg)',
                  borderRadius: '8px',
                  fontSize: '13px'
               }}>
                  {thinkingProcess.steps.map((step, idx) => (
                     <React.Fragment key={idx}>
                        <div style={{ 
                           padding: '8px 16px',
                           background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                           color: 'white',
                           borderRadius: '6px',
                           fontWeight: '500'
                        }}>
                           {step.agent}
                        </div>
                        {idx < thinkingProcess.steps.length - 1 && (
                           <ArrowRight size={16} color="#94a3b8" />
                        )}
                     </React.Fragment>
                  ))}
               </div>
               
               <div style={{ marginTop: '12px', fontSize: '12px', color: 'var(--text-muted)' }}>
                  Total Steps: {thinkingProcess.total_steps}
               </div>
            </div>
         )}

         {/* Token Usage Breakdown */}
         {tokenUsage.call_details && tokenUsage.call_details.length > 0 && (
            <details className="card" style={{ padding: '24px' }}>
               <summary style={{ fontSize: '14px', fontWeight: '600', cursor: 'pointer', marginBottom: '16px' }}>
                  Detailed Token Usage Breakdown
               </summary>
               <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '16px' }}>
                  {tokenUsage.call_details.map((call, idx) => (
                     <div 
                        key={idx}
                        style={{ 
                           padding: '12px',
                           background: 'var(--bg)',
                           borderRadius: '6px',
                           fontSize: '12px',
                           display: 'grid',
                           gridTemplateColumns: '1fr 1fr 1fr',
                           gap: '8px'
                        }}
                     >
                        <div>
                           <span style={{ color: 'var(--text-muted)' }}>Call {idx + 1}</span>
                        </div>
                        <div>
                           <span style={{ color: 'var(--text-muted)' }}>Prompt:</span> {call.prompt_tokens} | 
                           <span style={{ color: 'var(--text-muted)' }}> Completion:</span> {call.completion_tokens}
                        </div>
                        <div style={{ textAlign: 'right', fontWeight: '600' }}>
                           Total: {call.total_tokens}
                        </div>
                     </div>
                  ))}
               </div>
            </details>
         )}

      </div>
   );
}

export default AnalyticsDashboard;
