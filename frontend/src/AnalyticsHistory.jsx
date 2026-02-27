import React, { useState, useEffect } from 'react';
import {
   BarChart3,
   Clock,
   DollarSign,
   TrendingUp,
   FileText,
   Calendar,
   ArrowLeft
} from 'lucide-react';

function AnalyticsHistory({ onBack }) {
   const [sessions, setSessions] = useState([]);
   const [summary, setSummary] = useState(null);
   const [loading, setLoading] = useState(true);

   useEffect(() => {
      fetchAnalytics();
   }, []);

   const fetchAnalytics = async () => {
      try {
         const [sessionsRes, summaryRes] = await Promise.all([
            fetch('/analytics/sessions?limit=20'),
            fetch('/analytics/summary')
         ]);

         const sessionsData = await sessionsRes.json();
         const summaryData = await summaryRes.json();

         setSessions(sessionsData.sessions || []);
         setSummary(summaryData);
      } catch (error) {
         console.error('Failed to fetch analytics:', error);
      } finally {
         setLoading(false);
      }
   };

   if (loading) {
      return (
         <div style={{ minHeight: '100vh', padding: '40px 20px' }}>
            <div style={{ maxWidth: '1200px', margin: '0 auto', textAlign: 'center' }}>
               <div style={{
                  width: '48px',
                  height: '48px',
                  border: '3px solid #e2e8f0',
                  borderTopColor: '#2563eb',
                  borderRadius: '50%',
                  margin: '0 auto 16px',
                  animation: 'spin 0.8s linear infinite'
               }} />
               <p style={{ color: 'var(--text-muted)' }}>Loading analytics...</p>
            </div>
         </div>
      );
   }

   return (
      <div style={{ minHeight: '100vh', padding: '40px 20px' }}>
         <div style={{ maxWidth: '1200px', margin: '0 auto' }}>

            {/* Header */}
            <div style={{ marginBottom: '32px' }}>
               <button
                  onClick={onBack}
                  style={{
                     background: 'none',
                     border: 'none',
                     color: 'var(--primary)',
                     cursor: 'pointer',
                     display: 'flex',
                     alignItems: 'center',
                     gap: '8px',
                     fontSize: '14px',
                     marginBottom: '16px',
                     padding: '8px 0'
                  }}
               >
                  <ArrowLeft size={16} />
                  Back to Analyzer
               </button>

               <h1 style={{ fontSize: '28px', fontWeight: '600', marginBottom: '8px' }}>
                  Analytics History
               </h1>
               <p style={{ color: 'var(--text-muted)', margin: 0 }}>
                  Track token usage, costs, and performance metrics
               </p>
            </div>

            {/* Summary Cards */}
            {summary && (
               <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '20px', marginBottom: '32px' }}>

                  <div className="card" style={{ padding: '24px' }}>
                     <div style={{
                        width: '48px',
                        height: '48px',
                        borderRadius: '12px',
                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        marginBottom: '16px'
                     }}>
                        <FileText size={24} color="white" />
                     </div>
                     <div style={{ fontSize: '32px', fontWeight: '700', marginBottom: '4px' }}>
                        {summary.total_sessions}
                     </div>
                     <div style={{ fontSize: '14px', color: 'var(--text-muted)' }}>
                        Total Sessions
                     </div>
                  </div>

                  <div className="card" style={{ padding: '24px' }}>
                     <div style={{
                        width: '48px',
                        height: '48px',
                        borderRadius: '12px',
                        background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        marginBottom: '16px'
                     }}>
                        <BarChart3 size={24} color="white" />
                     </div>
                     <div style={{ fontSize: '32px', fontWeight: '700', marginBottom: '4px' }}>
                        {summary.total_tokens?.toLocaleString() || 0}
                     </div>
                     <div style={{ fontSize: '14px', color: 'var(--text-muted)' }}>
                        Total Tokens Used
                     </div>
                  </div>

                  <div className="card" style={{ padding: '24px' }}>
                     <div style={{
                        width: '48px',
                        height: '48px',
                        borderRadius: '12px',
                        background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        marginBottom: '16px'
                     }}>
                        <DollarSign size={24} color="white" />
                     </div>
                     <div style={{ fontSize: '32px', fontWeight: '700', marginBottom: '4px' }}>
                        ${summary.total_cost?.toFixed(4) || '0.0000'}
                     </div>
                     <div style={{ fontSize: '14px', color: 'var(--text-muted)' }}>
                        Total Cost
                     </div>
                  </div>

                  <div className="card" style={{ padding: '24px' }}>
                     <div style={{
                        width: '48px',
                        height: '48px',
                        borderRadius: '12px',
                        background: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        marginBottom: '16px'
                     }}>
                        <Clock size={24} color="white" />
                     </div>
                     <div style={{ fontSize: '32px', fontWeight: '700', marginBottom: '4px' }}>
                        {summary.average_duration?.toFixed(1) || 0}s
                     </div>
                     <div style={{ fontSize: '14px', color: 'var(--text-muted)' }}>
                        Avg Duration
                     </div>
                  </div>

               </div>
            )}

            {/* Sessions List */}
            <div className="card" style={{ padding: '24px' }}>
               <h2 style={{ fontSize: '18px', fontWeight: '600', marginBottom: '20px' }}>
                  Recent Sessions
               </h2>

               {sessions.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                     No sessions found. Analyze a PDF to get started.
                  </div>
               ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                     {sessions.map((session, idx) => (
                        <div
                           key={idx}
                           className="card"
                           style={{
                              padding: '20px',
                              background: 'var(--bg)',
                              border: '1px solid var(--border)',
                              transition: 'all 0.2s ease'
                           }}
                        >
                           <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '12px' }}>
                              <div>
                                 <div style={{ fontSize: '15px', fontWeight: '600', marginBottom: '4px' }}>
                                    {session.filename || 'Unknown File'}
                                 </div>
                                 <div style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                    <Calendar size={12} />
                                    {session.start_timestamp ? new Date(session.start_timestamp).toLocaleString() : 'N/A'}
                                 </div>
                              </div>
                              <div style={{
                                 padding: '4px 12px',
                                 background: session.failed_agents > 0 ? '#fef2f2' : '#f0fdf4',
                                 color: session.failed_agents > 0 ? '#991b1b' : '#166534',
                                 borderRadius: '12px',
                                 fontSize: '11px',
                                 fontWeight: '600'
                              }}>
                                 {session.failed_agents > 0 ? 'PARTIAL' : 'SUCCESS'}
                              </div>
                           </div>

                           <div style={{
                              display: 'grid',
                              gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                              gap: '16px',
                              paddingTop: '12px',
                              borderTop: '1px solid var(--border)'
                           }}>
                              <div>
                                 <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '2px' }}>
                                    Tokens
                                 </div>
                                 <div style={{ fontSize: '14px', fontWeight: '600' }}>
                                    {session.total_tokens?.toLocaleString() || 0}
                                 </div>
                              </div>

                              <div>
                                 <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '2px' }}>
                                    Cost
                                 </div>
                                 <div style={{ fontSize: '14px', fontWeight: '600' }}>
                                    ${session.estimated_cost_usd?.toFixed(6) || '0.000000'}
                                 </div>
                              </div>

                              <div>
                                 <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '2px' }}>
                                    Duration
                                 </div>
                                 <div style={{ fontSize: '14px', fontWeight: '600' }}>
                                    {session.total_duration_seconds?.toFixed(2) || 0}s
                                 </div>
                              </div>

                              <div>
                                 <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '2px' }}>
                                    Agents
                                 </div>
                                 <div style={{ fontSize: '14px', fontWeight: '600' }}>
                                    {session.successful_agents || 0} / {(session.successful_agents || 0) + (session.failed_agents || 0)}
                                 </div>
                              </div>
                           </div>
                        </div>
                     ))}
                  </div>
               )}
            </div>

         </div>
      </div>
   );
}

export default AnalyticsHistory;
