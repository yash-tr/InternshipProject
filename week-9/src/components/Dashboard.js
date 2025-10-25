import React, { useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { Link } from 'react-router-dom';
import { fetchUserData } from '../store/slices/userSlice';
import { openModal } from '../store/slices/modalSlice';
import { addNotification } from '../store/slices/uiSlice';
import styled from 'styled-components';

const DashboardContainer = styled.div`
  padding: 24px 0;
`;

const WelcomeSection = styled.div`
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 32px;
  border-radius: 12px;
  margin-bottom: 32px;
  text-align: center;
`;

const WelcomeTitle = styled.h1`
  margin: 0 0 16px 0;
  font-size: 32px;
  font-weight: 700;
`;

const WelcomeSubtitle = styled.p`
  margin: 0;
  font-size: 18px;
  opacity: 0.9;
`;

const StatsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 24px;
  margin-bottom: 32px;
`;

const StatCard = styled.div`
  background: white;
  padding: 24px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  text-align: center;
`;

const StatIcon = styled.div`
  font-size: 32px;
  margin-bottom: 16px;
`;

const StatValue = styled.div`
  font-size: 28px;
  font-weight: bold;
  color: #333;
  margin-bottom: 8px;
`;

const StatLabel = styled.div`
  color: #666;
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

const ActionGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 24px;
`;

const ActionCard = styled.div`
  background: white;
  padding: 24px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  text-align: center;
`;

const ActionIcon = styled.div`
  font-size: 48px;
  margin-bottom: 16px;
`;

const ActionTitle = styled.h3`
  margin: 0 0 12px 0;
  color: #333;
  font-size: 20px;
`;

const ActionDescription = styled.p`
  margin: 0 0 20px 0;
  color: #666;
  line-height: 1.5;
`;

const Dashboard = () => {
  const dispatch = useDispatch();
  const { user, loading } = useSelector(state => state.user);
  const { notifications } = useSelector(state => state.ui);

  useEffect(() => {
    if (!user) {
      dispatch(fetchUserData());
    }
  }, [dispatch, user]);

  const handleQuickStart = () => {
    dispatch(openModal({
      type: 'info',
      title: 'Quick Start Guide',
      props: {
        icon: '🚀',
        description: 'Welcome to the enhanced resume builder! Our new parsing flow will automatically extract and organize your information for faster resume creation.'
      }
    }));
  };

  const handleShowNotifications = () => {
    dispatch(addNotification({
      message: 'This is a targeted notification for Diwali support hours!',
      type: 'info'
    }));
  };

  const handlePackageFlow = () => {
    dispatch(openModal({
      type: 'confirmation',
      title: 'New Package Flow',
      props: {
        message: 'This demonstrates the overridden package button triggering the new product flow as requested by product team.',
        onConfirm: () => {
          console.log('New package flow initiated!');
          dispatch(addNotification({
            message: 'New package flow initiated successfully!',
            type: 'success'
          }));
        }
      }
    }));
  };

  if (loading) {
    return (
      <DashboardContainer>
        <div className="loading">Loading dashboard...</div>
      </DashboardContainer>
    );
  }

  return (
    <DashboardContainer>
      <WelcomeSection>
        <WelcomeTitle>
          Welcome back, {user?.name || 'User'}! 👋
        </WelcomeTitle>
        <WelcomeSubtitle>
          Your enhanced resume builder is ready with new parsing capabilities and improved performance.
        </WelcomeSubtitle>
      </WelcomeSection>

      <StatsGrid>
        <StatCard>
          <StatIcon>📊</StatIcon>
          <StatValue>98%</StatValue>
          <StatLabel>Automation Success Rate</StatLabel>
        </StatCard>
        
        <StatCard>
          <StatIcon>⚡</StatIcon>
          <StatValue>2.1s</StatValue>
          <StatLabel>Avg Generation Time</StatLabel>
        </StatCard>
        
        <StatCard>
          <StatIcon>👥</StatIcon>
          <StatValue>200</StatValue>
          <StatLabel>Beta Test Users</StatLabel>
        </StatCard>
        
        <StatCard>
          <StatIcon>🎯</StatIcon>
          <StatValue>85%</StatValue>
          <StatLabel>Completion Rate</StatLabel>
        </StatCard>
      </StatsGrid>

      <ActionGrid>
        <ActionCard>
          <ActionIcon>📝</ActionIcon>
          <ActionTitle>Resume Builder</ActionTitle>
          <ActionDescription>
            Create professional resumes with our enhanced builder featuring automatic parsing and improved templates.
          </ActionDescription>
          <Link to="/resume-builder" className="btn btn-primary">
            Start Building
          </Link>
        </ActionCard>

        <ActionCard>
          <ActionIcon>🎉</ActionIcon>
          <ActionTitle>Diwali Event</ActionTitle>
          <ActionDescription>
            Join our special Diwali event page with limited-time offers and festive celebrations.
          </ActionDescription>
          <Link to="/event" className="btn btn-success">
            View Event
          </Link>
        </ActionCard>

        <ActionCard>
          <ActionIcon>🔧</ActionIcon>
          <ActionTitle>Quick Start Guide</ActionTitle>
          <ActionDescription>
            Learn about the new features and improvements in our resume builder.
          </ActionDescription>
          <button className="btn btn-secondary" onClick={handleQuickStart}>
            View Guide
          </button>
        </ActionCard>

        <ActionCard>
          <ActionIcon>📦</ActionIcon>
          <ActionTitle>Package Flow Demo</ActionTitle>
          <ActionDescription>
            Experience the new package flow override that triggers enhanced backend processes.
          </ActionDescription>
          <button className="btn btn-primary" onClick={handlePackageFlow}>
            Try New Flow
          </button>
        </ActionCard>

        <ActionCard>
          <ActionIcon>🔔</ActionIcon>
          <ActionTitle>Notifications</ActionTitle>
          <ActionDescription>
            Test our targeted notification system for Diwali support hours and user segments.
          </ActionDescription>
          <button className="btn btn-secondary" onClick={handleShowNotifications}>
            Show Notification
          </button>
        </ActionCard>

        <ActionCard>
          <ActionIcon>🎨</ActionIcon>
          <ActionTitle>Component Demo</ActionTitle>
          <ActionDescription>
            Explore the new conditional modal component with different layouts and content types.
          </ActionDescription>
          <button 
            className="btn btn-primary"
            onClick={() => dispatch(openModal({
              type: 'custom',
              title: 'Custom Modal Layout',
              layout: 'wide',
              content: (
                <div style={{ padding: '20px', textAlign: 'center' }}>
                  <h3>🎨 Custom Modal Content</h3>
                  <p>This demonstrates the flexible modal component with custom content and wide layout.</p>
                  <div style={{ 
                    display: 'grid', 
                    gridTemplateColumns: 'repeat(2, 1fr)', 
                    gap: '16px', 
                    marginTop: '20px' 
                  }}>
                    <div style={{ padding: '16px', backgroundColor: '#f8f9fa', borderRadius: '8px' }}>
                      <strong>Feature 1:</strong> Conditional rendering
                    </div>
                    <div style={{ padding: '16px', backgroundColor: '#f8f9fa', borderRadius: '8px' }}>
                      <strong>Feature 2:</strong> Dynamic layouts
                    </div>
                  </div>
                </div>
              )
            }))}
          >
            Demo Modal
          </button>
        </ActionCard>
      </ActionGrid>

      {notifications.length > 0 && (
        <div style={{ marginTop: '32px' }}>
          <h3>Recent Notifications</h3>
          {notifications.slice(-3).map(notification => (
            <div key={notification.id} className="card">
              <strong>{notification.type.toUpperCase()}:</strong> {notification.message}
              <small style={{ display: 'block', color: '#666', marginTop: '8px' }}>
                {new Date(notification.timestamp).toLocaleString()}
              </small>
            </div>
          ))}
        </div>
      )}
    </DashboardContainer>
  );
};

export default Dashboard;
