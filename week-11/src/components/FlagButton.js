import React from 'react';
import { useDispatch } from 'react-redux';
import { openFlaggingModal } from '../store/slices/flaggingSlice';
import styled from 'styled-components';

const FlagButtonStyled = styled.button`
  background: transparent;
  border: 1px solid #dc3545;
  color: #dc3545;
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: all 0.2s;
  
  &:hover {
    background: #dc3545;
    color: white;
  }
  
  svg {
    width: 14px;
    height: 14px;
  }
`;

const FlagButton = ({ entityType, entityId, className }) => {
  const dispatch = useDispatch();

  const handleClick = (e) => {
    e.stopPropagation();
    dispatch(openFlaggingModal({
      entityType,
      entityId
    }));
  };

  return (
    <FlagButtonStyled onClick={handleClick} className={className}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/>
        <line x1="4" y1="22" x2="4" y2="15"/>
      </svg>
      Flag
    </FlagButtonStyled>
  );
};

export default FlagButton;

