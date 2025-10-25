import React from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { closeModal } from '../store/slices/modalSlice';
import styled from 'styled-components';

const ModalOverlay = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
`;

const ModalContainer = styled.div`
  background: white;
  border-radius: 12px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
  max-width: ${props => props.layout === 'wide' ? '800px' : '500px'};
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  position: relative;
`;

const ModalHeader = styled.div`
  padding: 24px 24px 0 24px;
  border-bottom: 1px solid #e9ecef;
  margin-bottom: 24px;
`;

const ModalTitle = styled.h2`
  margin: 0;
  color: #333;
  font-size: 24px;
  font-weight: 600;
`;

const ModalBody = styled.div`
  padding: 0 24px 24px 24px;
`;

const ModalFooter = styled.div`
  padding: 16px 24px;
  border-top: 1px solid #e9ecef;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
`;

const CloseButton = styled.button`
  position: absolute;
  top: 16px;
  right: 16px;
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #666;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  
  &:hover {
    background-color: #f8f9fa;
    color: #333;
  }
`;

const ConditionalModal = () => {
  const dispatch = useDispatch();
  const { isOpen, modalType, modalProps, content, layout } = useSelector(state => state.modal);

  const handleClose = () => {
    dispatch(closeModal());
  };

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) {
      handleClose();
    }
  };

  if (!isOpen) return null;

  const renderModalContent = () => {
    switch (modalType) {
      case 'confirmation':
        return (
          <div>
            <p>{modalProps.message || 'Are you sure you want to proceed?'}</p>
            <div style={{ display: 'flex', gap: '12px', marginTop: '20px' }}>
              <button 
                className="btn btn-primary"
                onClick={() => {
                  modalProps.onConfirm?.();
                  handleClose();
                }}
              >
                Confirm
              </button>
              <button 
                className="btn btn-secondary"
                onClick={handleClose}
              >
                Cancel
              </button>
            </div>
          </div>
        );

      case 'form':
        return (
          <div>
            <form onSubmit={(e) => {
              e.preventDefault();
              modalProps.onSubmit?.(new FormData(e.target));
              handleClose();
            }}>
              {modalProps.fields?.map((field, index) => (
                <div key={index} style={{ marginBottom: '16px' }}>
                  <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
                    {field.label}
                  </label>
                  <input
                    type={field.type || 'text'}
                    name={field.name}
                    required={field.required}
                    style={{
                      width: '100%',
                      padding: '12px',
                      border: '1px solid #ddd',
                      borderRadius: '6px',
                      fontSize: '16px'
                    }}
                  />
                </div>
              ))}
              <div style={{ display: 'flex', gap: '12px', marginTop: '20px' }}>
                <button type="submit" className="btn btn-primary">
                  Submit
                </button>
                <button type="button" className="btn btn-secondary" onClick={handleClose}>
                  Cancel
                </button>
              </div>
            </form>
          </div>
        );

      case 'info':
        return (
          <div>
            <div style={{ 
              padding: '20px', 
              backgroundColor: '#f8f9fa', 
              borderRadius: '8px',
              marginBottom: '20px'
            }}>
              {modalProps.icon && <span style={{ fontSize: '24px', marginRight: '12px' }}>{modalProps.icon}</span>}
              {modalProps.description}
            </div>
            <div style={{ display: 'flex', gap: '12px' }}>
              <button className="btn btn-primary" onClick={handleClose}>
                Got it
              </button>
            </div>
          </div>
        );

      case 'custom':
        return content;

      default:
        return (
          <div>
            <p>Default modal content</p>
            <button className="btn btn-primary" onClick={handleClose}>
              Close
            </button>
          </div>
        );
    }
  };

  return (
    <ModalOverlay onClick={handleBackdropClick}>
      <ModalContainer layout={layout}>
        <CloseButton onClick={handleClose}>×</CloseButton>
        
        <ModalHeader>
          <ModalTitle>{modalProps.title || 'Modal'}</ModalTitle>
        </ModalHeader>
        
        <ModalBody>
          {renderModalContent()}
        </ModalBody>
        
        {modalProps.showFooter !== false && (
          <ModalFooter>
            {modalProps.footerActions?.map((action, index) => (
              <button
                key={index}
                className={`btn ${action.className || 'btn-secondary'}`}
                onClick={() => {
                  action.onClick?.();
                  if (action.closeOnClick !== false) {
                    handleClose();
                  }
                }}
              >
                {action.label}
              </button>
            ))}
          </ModalFooter>
        )}
      </ModalContainer>
    </ModalOverlay>
  );
};

export default ConditionalModal;
