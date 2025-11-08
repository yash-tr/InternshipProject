import React, { useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { checkBlockStatus } from '../store/slices/userSlice';
import styled from 'styled-components';

const BlockerOverlay = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 99999;
`;

const BlockerContent = styled.div`
  background: white;
  border-radius: 12px;
  padding: 40px;
  max-width: 500px;
  text-align: center;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
`;

const BlockerIcon = styled.div`
  font-size: 64px;
  margin-bottom: 24px;
`;

const BlockerTitle = styled.h2`
  margin: 0 0 16px 0;
  color: #dc3545;
  font-size: 24px;
`;

const BlockerMessage = styled.p`
  margin: 0 0 24px 0;
  color: #666;
  line-height: 1.6;
  font-size: 16px;
`;

const BlockerReason = styled.div`
  background: #f8f9fa;
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 24px;
  text-align: left;
`;

const ReasonTitle = styled.h4`
  margin: 0 0 8px 0;
  color: #333;
  font-size: 14px;
  font-weight: 600;
`;

const ReasonText = styled.p`
  margin: 0;
  color: #666;
  font-size: 14px;
`;

const ContactInfo = styled.div`
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid #eee;
`;

const ContactText = styled.p`
  margin: 0;
  color: #666;
  font-size: 14px;
  
  a {
    color: #007bff;
    text-decoration: none;
    
    &:hover {
      text-decoration: underline;
    }
  }
`;

const JobPortalBlocker = () => {
  const dispatch = useDispatch();
  const { user, blockStatus } = useSelector(state => state.user);

  useEffect(() => {
    if (user && user.id) {
      dispatch(checkBlockStatus(user.id));
    }
  }, [dispatch, user]);

  if (!blockStatus || !blockStatus.is_blocked) {
    return null;
  }

  const block = blockStatus.block;

  return (
    <BlockerOverlay>
      <BlockerContent>
        <BlockerIcon>🚫</BlockerIcon>
        <BlockerTitle>Access Restricted</BlockerTitle>
        <BlockerMessage>
          Your access to the job portal has been restricted due to a policy violation.
        </BlockerMessage>

        {block && (
          <BlockerReason>
            <ReasonTitle>Reason:</ReasonTitle>
            <ReasonText>{block.reason}</ReasonText>
            {block.expires_at && (
              <ReasonText style={{ marginTop: '8px', fontSize: '12px', color: '#999' }}>
                This restriction will be lifted on {new Date(block.expires_at).toLocaleDateString()}
              </ReasonText>
            )}
          </BlockerReason>
        )}

        <ContactInfo>
          <ContactText>
            If you believe this is an error, please contact our support team at{' '}
            <a href="mailto:support@example.com">support@example.com</a>
          </ContactText>
        </ContactInfo>
      </BlockerContent>
    </BlockerOverlay>
  );
};

export default JobPortalBlocker;

