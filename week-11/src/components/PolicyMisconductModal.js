import React, { useState, useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { closePolicyModal, acknowledgePolicy } from '../store/slices/policySlice';
import { trackModalInteraction } from '../services/analyticsService';
import styled from 'styled-components';

const ModalOverlay = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
`;

const ModalContent = styled.div`
  background: white;
  border-radius: 12px;
  padding: 32px;
  max-width: 600px;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
`;

const ModalHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
`;

const ModalTitle = styled.h2`
  margin: 0;
  color: #333;
  font-size: 24px;
`;

const CloseButton = styled.button`
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #666;
  
  &:hover {
    color: #333;
  }
`;

const PolicyContent = styled.div`
  margin-bottom: 24px;
  line-height: 1.6;
  color: #555;
  
  h3 {
    color: #333;
    margin-top: 20px;
    margin-bottom: 10px;
  }
  
  p {
    margin-bottom: 12px;
  }
  
  ul {
    margin-left: 20px;
    margin-bottom: 12px;
  }
`;

const SeverityBadge = styled.span`
  display: inline-block;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: bold;
  margin-bottom: 16px;
  
  ${props => {
    switch(props.severity) {
      case 'critical':
        return 'background: #dc3545; color: white;';
      case 'error':
        return 'background: #f8d7da; color: #721c24;';
      case 'warning':
        return 'background: #fff3cd; color: #856404;';
      default:
        return 'background: #d1ecf1; color: #0c5460;';
    }
  }}
`;

const ModalFooter = styled.div`
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
`;

const Button = styled.button`
  padding: 10px 24px;
  border-radius: 6px;
  border: none;
  font-size: 16px;
  cursor: pointer;
  font-weight: 500;
  
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
`;

const PrimaryButton = styled(Button)`
  background: #007bff;
  color: white;
  
  &:hover:not(:disabled) {
    background: #0056b3;
  }
`;

const SecondaryButton = styled(Button)`
  background: #6c757d;
  color: white;
  
  &:hover:not(:disabled) {
    background: #545b62;
  }
`;

const PolicyMisconductModal = () => {
  const dispatch = useDispatch();
  const { isOpen, policy, loading } = useSelector(state => state.policy);
  const { user } = useSelector(state => state.user);
  const [acknowledging, setAcknowledging] = useState(false);

  useEffect(() => {
    if (isOpen && policy) {
      trackModalInteraction(user, 'policy_misconduct_modal', 'opened', {
        policy_id: policy.id,
        policy_version: policy.version
      });
    }
  }, [isOpen, policy, user]);

  const handleClose = () => {
    if (!policy.requires_acknowledgment) {
      dispatch(closePolicyModal());
      trackModalInteraction(user, 'policy_misconduct_modal', 'closed');
    }
  };

  const handleAcknowledge = async () => {
    setAcknowledging(true);
    
    try {
      await dispatch(acknowledgePolicy(policy.id)).unwrap();
      
      trackModalInteraction(user, 'policy_misconduct_modal', 'acknowledged', {
        policy_id: policy.id,
        policy_version: policy.version
      });
      
      dispatch(closePolicyModal());
    } catch (error) {
      console.error('Error acknowledging policy:', error);
    } finally {
      setAcknowledging(false);
    }
  };

  if (!isOpen || !policy) return null;

  return (
    <ModalOverlay onClick={handleClose}>
      <ModalContent onClick={(e) => e.stopPropagation()}>
        <ModalHeader>
          <ModalTitle>{policy.title}</ModalTitle>
          {!policy.requires_acknowledgment && (
            <CloseButton onClick={handleClose}>×</CloseButton>
          )}
        </ModalHeader>

        <SeverityBadge severity={policy.severity_level}>
          {policy.severity_level.toUpperCase()}
        </SeverityBadge>

        <PolicyContent dangerouslySetInnerHTML={{ __html: policy.content }} />

        <ModalFooter>
          {policy.requires_acknowledgment ? (
            <PrimaryButton
              onClick={handleAcknowledge}
              disabled={acknowledging || loading}
            >
              {acknowledging ? 'Processing...' : 'I Understand'}
            </PrimaryButton>
          ) : (
            <>
              <SecondaryButton onClick={handleClose}>
                Close
              </SecondaryButton>
              <PrimaryButton onClick={handleAcknowledge} disabled={acknowledging}>
                Acknowledge
              </PrimaryButton>
            </>
          )}
        </ModalFooter>
      </ModalContent>
    </ModalOverlay>
  );
};

export default PolicyMisconductModal;

