import React from 'react';
import styled from 'styled-components';

const BannerContainer = styled.div`
  background: linear-gradient(135deg, #ff6b6b 0%, #ffa500 100%);
  color: white;
  padding: 16px 24px;
  text-align: center;
  position: relative;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
`;

const BannerContent = styled.div`
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  flex-wrap: wrap;
`;

const BannerText = styled.div`
  font-size: 16px;
  font-weight: 500;
  line-height: 1.4;
`;

const BannerIcon = styled.span`
  font-size: 20px;
  margin-right: 8px;
`;

const CloseButton = styled.button`
  position: absolute;
  top: 8px;
  right: 16px;
  background: none;
  border: none;
  color: white;
  font-size: 20px;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  
  &:hover {
    background-color: rgba(255, 255, 255, 0.1);
  }
`;

const SupportHours = styled.div`
  background: rgba(255, 255, 255, 0.1);
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 600;
  margin-left: 16px;
`;

const DiwaliBanner = ({ onClose }) => {
  return (
    <BannerContainer>
      <CloseButton onClick={onClose} aria-label="Close banner">
        ×
      </CloseButton>
      
      <BannerContent>
        <BannerIcon>🎉</BannerIcon>
        <BannerText>
          <strong>Diwali Special:</strong> Limited support hours during festival week. 
          Our team will be available 10 AM - 2 PM IST. 
          Wishing you a Happy Diwali! 🪔
        </BannerText>
        <SupportHours>
          Support: 10 AM - 2 PM IST
        </SupportHours>
      </BannerContent>
    </BannerContainer>
  );
};

export default DiwaliBanner;
