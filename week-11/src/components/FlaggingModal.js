import React, { useState } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { closeFlaggingModal, submitFlag } from '../store/slices/flaggingSlice';
import { trackModalInteraction, trackFlagging } from '../services/analyticsService';
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
  max-width: 500px;
  width: 90%;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
`;

const ModalHeader = styled.div`
  margin-bottom: 24px;
`;

const ModalTitle = styled.h2`
  margin: 0 0 8px 0;
  color: #333;
  font-size: 24px;
`;

const ModalSubtitle = styled.p`
  margin: 0;
  color: #666;
  font-size: 14px;
`;

const FormGroup = styled.div`
  margin-bottom: 20px;
`;

const Label = styled.label`
  display: block;
  margin-bottom: 8px;
  color: #333;
  font-weight: 500;
  font-size: 14px;
`;

const Select = styled.select`
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  
  &:focus {
    outline: none;
    border-color: #007bff;
  }
`;

const TextArea = styled.textarea`
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  min-height: 100px;
  resize: vertical;
  
  &:focus {
    outline: none;
    border-color: #007bff;
  }
`;

const Input = styled.input`
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  
  &:focus {
    outline: none;
    border-color: #007bff;
  }
`;

const SeverityIndicator = styled.div`
  margin-top: 8px;
  padding: 8px;
  border-radius: 4px;
  font-size: 12px;
  
  ${props => {
    switch(props.severity) {
      case 'critical':
        return 'background: #f8d7da; color: #721c24;';
      case 'high':
        return 'background: #fff3cd; color: #856404;';
      case 'medium':
        return 'background: #d1ecf1; color: #0c5460;';
      default:
        return 'background: #d4edda; color: #155724;';
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
  background: #dc3545;
  color: white;
  
  &:hover:not(:disabled) {
    background: #c82333;
  }
`;

const SecondaryButton = styled(Button)`
  background: #6c757d;
  color: white;
  
  &:hover:not(:disabled) {
    background: #545b62;
  }
`;

const FlaggingModal = () => {
  const dispatch = useDispatch();
  const { isOpen, entityType, entityId, loading } = useSelector(state => state.flagging);
  const { user } = useSelector(state => state.user);

  const [formData, setFormData] = useState({
    violation_type: '',
    severity: 'medium',
    reason: '',
    details: '',
    evidence_urls: ''
  });

  const violationTypes = [
    { value: 'spam', label: 'Spam' },
    { value: 'inappropriate_content', label: 'Inappropriate Content' },
    { value: 'fake_information', label: 'Fake Information' },
    { value: 'harassment', label: 'Harassment' },
    { value: 'copyright_violation', label: 'Copyright Violation' },
    { value: 'privacy_violation', label: 'Privacy Violation' },
    { value: 'other', label: 'Other' }
  ];

  const severities = [
    { value: 'low', label: 'Low' },
    { value: 'medium', label: 'Medium' },
    { value: 'high', label: 'High' },
    { value: 'critical', label: 'Critical' }
  ];

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!formData.violation_type || !formData.reason) {
      alert('Please fill in all required fields');
      return;
    }

    try {
      await dispatch(submitFlag({
        flagged_entity_type: entityType,
        flagged_entity_id: entityId,
        ...formData
      })).unwrap();

      trackFlagging(user, formData.violation_type, {
        entity_type: entityType,
        entity_id: entityId,
        severity: formData.severity
      });

      dispatch(closeFlaggingModal());
      alert('Flag submitted successfully');
    } catch (error) {
      console.error('Error submitting flag:', error);
      alert('Failed to submit flag. Please try again.');
    }
  };

  const handleClose = () => {
    dispatch(closeFlaggingModal());
  };

  if (!isOpen) return null;

  return (
    <ModalOverlay onClick={handleClose}>
      <ModalContent onClick={(e) => e.stopPropagation()}>
        <ModalHeader>
          <ModalTitle>Flag Content</ModalTitle>
          <ModalSubtitle>Report a violation of our platform policies</ModalSubtitle>
        </ModalHeader>

        <form onSubmit={handleSubmit}>
          <FormGroup>
            <Label>Violation Type *</Label>
            <Select
              name="violation_type"
              value={formData.violation_type}
              onChange={handleChange}
              required
            >
              <option value="">Select violation type</option>
              {violationTypes.map(type => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </Select>
          </FormGroup>

          <FormGroup>
            <Label>Severity *</Label>
            <Select
              name="severity"
              value={formData.severity}
              onChange={handleChange}
              required
            >
              {severities.map(severity => (
                <option key={severity.value} value={severity.value}>
                  {severity.label}
                </option>
              ))}
            </Select>
            <SeverityIndicator severity={formData.severity}>
              {formData.severity === 'critical' && 'This will trigger immediate review'}
              {formData.severity === 'high' && 'This will be reviewed within 24 hours'}
            </SeverityIndicator>
          </FormGroup>

          <FormGroup>
            <Label>Reason *</Label>
            <TextArea
              name="reason"
              value={formData.reason}
              onChange={handleChange}
              placeholder="Brief description of the violation"
              required
            />
          </FormGroup>

          <FormGroup>
            <Label>Details</Label>
            <TextArea
              name="details"
              value={formData.details}
              onChange={handleChange}
              placeholder="Additional details (optional)"
            />
          </FormGroup>

          <FormGroup>
            <Label>Evidence URLs</Label>
            <Input
              type="text"
              name="evidence_urls"
              value={formData.evidence_urls}
              onChange={handleChange}
              placeholder="Comma-separated URLs (optional)"
            />
          </FormGroup>

          <ModalFooter>
            <SecondaryButton type="button" onClick={handleClose}>
              Cancel
            </SecondaryButton>
            <PrimaryButton type="submit" disabled={loading}>
              {loading ? 'Submitting...' : 'Submit Flag'}
            </PrimaryButton>
          </ModalFooter>
        </form>
      </ModalContent>
    </ModalOverlay>
  );
};

export default FlaggingModal;

