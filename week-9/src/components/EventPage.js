import React from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { openModal } from '../store/slices/modalSlice';
import { addNotification } from '../store/slices/uiSlice';
import styled from 'styled-components';

const EventContainer = styled.div`
  padding: 24px 0;
`;

const EventHeader = styled.div`
  background: linear-gradient(135deg, #ff6b6b 0%, #ffa500 100%);
  color: white;
  padding: 48px 32px;
  border-radius: 16px;
  text-align: center;
  margin-bottom: 32px;
  position: relative;
  overflow: hidden;
`;

const EventTitle = styled.h1`
  margin: 0 0 16px 0;
  font-size: 48px;
  font-weight: 700;
  text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
`;

const EventSubtitle = styled.p`
  margin: 0 0 24px 0;
  font-size: 20px;
  opacity: 0.9;
`;

const EventDate = styled.div`
  background: rgba(255, 255, 255, 0.2);
  padding: 12px 24px;
  border-radius: 25px;
  display: inline-block;
  font-weight: 600;
  backdrop-filter: blur(10px);
`;

const DecorativeElements = styled.div`
  position: absolute;
  top: 20px;
  right: 20px;
  font-size: 32px;
  opacity: 0.3;
`;

const ContentGrid = styled.div`
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 32px;
  
  @media (max-width: 768px) {
    grid-template-columns: 1fr;
  }
`;

const MainContent = styled.div`
  background: white;
  padding: 32px;
  border-radius: 16px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
`;

const Sidebar = styled.div`
  display: flex;
  flex-direction: column;
  gap: 24px;
`;

const SidebarCard = styled.div`
  background: white;
  padding: 24px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
`;

const SectionTitle = styled.h3`
  margin: 0 0 20px 0;
  color: #333;
  font-size: 24px;
  display: flex;
  align-items: center;
  gap: 12px;
`;

const FeatureList = styled.ul`
  list-style: none;
  padding: 0;
  margin: 0;
`;

const FeatureItem = styled.li`
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  gap: 12px;
  
  &:last-child {
    border-bottom: none;
  }
`;

const FeatureIcon = styled.span`
  font-size: 20px;
`;

const FeatureText = styled.span`
  color: #333;
  font-weight: 500;
`;

const SupportHours = styled.div`
  background: linear-gradient(135deg, #ff6b6b 0%, #ffa500 100%);
  color: white;
  padding: 20px;
  border-radius: 12px;
  text-align: center;
  margin-bottom: 20px;
`;

const SupportTitle = styled.h4`
  margin: 0 0 12px 0;
  font-size: 18px;
`;

const SupportTime = styled.div`
  font-size: 24px;
  font-weight: bold;
  margin-bottom: 8px;
`;

const SupportNote = styled.div`
  font-size: 14px;
  opacity: 0.9;
`;

const EventPage = () => {
  const dispatch = useDispatch();
  const { user } = useSelector(state => state.user);

  const handleSpecialOffer = () => {
    dispatch(openModal({
      type: 'info',
      title: '🎉 Diwali Special Offer',
      layout: 'wide',
      props: {
        icon: '🎁',
        description: 'Get 50% off on premium features during our Diwali celebration! This limited-time offer includes advanced templates, priority support, and unlimited resume generations.'
      }
    }));
  };

  const handleSupportNotification = () => {
    dispatch(addNotification({
      message: 'Diwali Support Hours: 10 AM - 2 PM IST. Limited support during festival week.',
      type: 'warning'
    }));
  };

  const handleEventRegistration = () => {
    dispatch(openModal({
      type: 'form',
      title: 'Register for Diwali Event',
      props: {
        fields: [
          { name: 'name', label: 'Full Name', required: true },
          { name: 'email', label: 'Email Address', type: 'email', required: true },
          { name: 'phone', label: 'Phone Number', type: 'tel' },
          { name: 'interests', label: 'Areas of Interest', type: 'textarea' }
        ],
        onSubmit: (formData) => {
          console.log('Event registration:', formData);
          dispatch(addNotification({
            message: 'Successfully registered for Diwali event! You will receive a confirmation email shortly.',
            type: 'success'
          }));
        }
      }
    }));
  };

  return (
    <EventContainer>
      <EventHeader>
        <DecorativeElements>🪔✨🎆</DecorativeElements>
        <EventTitle>Diwali Celebration 2025</EventTitle>
        <EventSubtitle>
          Join us for a festive celebration with special offers and limited-time features
        </EventSubtitle>
        <EventDate>November 1-5, 2025</EventDate>
      </EventHeader>

      <ContentGrid>
        <MainContent>
          <SectionTitle>
            🎉 Event Highlights
          </SectionTitle>
          
          <FeatureList>
            <FeatureItem>
              <FeatureIcon>🎁</FeatureIcon>
              <FeatureText>50% off on all premium features</FeatureText>
            </FeatureItem>
            <FeatureItem>
              <FeatureIcon>🎨</FeatureIcon>
              <FeatureText>Exclusive Diwali-themed resume templates</FeatureText>
            </FeatureItem>
            <FeatureItem>
              <FeatureIcon>⚡</FeatureIcon>
              <FeatureText>Priority processing for all resume generations</FeatureText>
            </FeatureItem>
            <FeatureItem>
              <FeatureIcon>🎯</FeatureIcon>
              <FeatureText>Special AI-powered content enhancement</FeatureText>
            </FeatureItem>
            <FeatureItem>
              <FeatureIcon>📱</FeatureIcon>
              <FeatureText>Mobile-optimized experience for on-the-go creation</FeatureText>
            </FeatureItem>
            <FeatureItem>
              <FeatureIcon>🔔</FeatureIcon>
              <FeatureText>Personalized notifications and updates</FeatureText>
            </FeatureItem>
          </FeatureList>

          <div style={{ marginTop: '32px', textAlign: 'center' }}>
            <button 
              className="btn btn-primary"
              onClick={handleSpecialOffer}
              style={{ marginRight: '12px' }}
            >
              View Special Offers
            </button>
            
            <button 
              className="btn btn-success"
              onClick={handleEventRegistration}
            >
              Register for Event
            </button>
          </div>
        </MainContent>

        <Sidebar>
          <SidebarCard>
            <SectionTitle>🕐 Support Hours</SectionTitle>
            <SupportHours>
              <SupportTitle>Diwali Support Schedule</SupportTitle>
              <SupportTime>10 AM - 2 PM IST</SupportTime>
              <SupportNote>
                Limited support during festival week
              </SupportNote>
            </SupportHours>
            
            <button 
              className="btn btn-secondary"
              onClick={handleSupportNotification}
              style={{ width: '100%' }}
            >
              Get Support Notification
            </button>
          </SidebarCard>

          <SidebarCard>
            <SectionTitle>📊 Event Stats</SectionTitle>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#007bff', marginBottom: '8px' }}>
                1,247
              </div>
              <div style={{ color: '#666', marginBottom: '20px' }}>
                Registered Participants
              </div>
              
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#28a745', marginBottom: '8px' }}>
                98%
              </div>
              <div style={{ color: '#666', marginBottom: '20px' }}>
                User Satisfaction
              </div>
              
              <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#ffc107', marginBottom: '8px' }}>
                2.1s
              </div>
              <div style={{ color: '#666' }}>
                Avg Generation Time
              </div>
            </div>
          </SidebarCard>

          <SidebarCard>
            <SectionTitle>🎯 Quick Actions</SectionTitle>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <button 
                className="btn btn-primary"
                onClick={() => window.location.href = '/resume-builder'}
              >
                Create Resume
              </button>
              
              <button 
                className="btn btn-secondary"
                onClick={handleSpecialOffer}
              >
                View Offers
              </button>
              
              <button 
                className="btn btn-success"
                onClick={handleEventRegistration}
              >
                Join Event
              </button>
            </div>
          </SidebarCard>
        </Sidebar>
      </ContentGrid>
    </EventContainer>
  );
};

export default EventPage;
