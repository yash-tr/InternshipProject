import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useSelector, useDispatch } from 'react-redux';
import { openModal } from '../store/slices/modalSlice';
import { toggleTheme } from '../store/slices/uiSlice';
import styled from 'styled-components';

const Nav = styled.nav`
  background: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  padding: 0 24px;
  position: sticky;
  top: 0;
  z-index: 100;
`;

const NavContainer = styled.div`
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 64px;
`;

const Logo = styled(Link)`
  font-size: 24px;
  font-weight: bold;
  color: #007bff;
  text-decoration: none;
  
  &:hover {
    color: #0056b3;
  }
`;

const NavLinks = styled.div`
  display: flex;
  gap: 24px;
  align-items: center;
`;

const NavLink = styled(Link)`
  color: ${props => props.active ? '#007bff' : '#333'};
  text-decoration: none;
  font-weight: ${props => props.active ? '600' : '400'};
  padding: 8px 16px;
  border-radius: 6px;
  transition: all 0.2s ease;
  
  &:hover {
    background-color: #f8f9fa;
    color: #007bff;
  }
`;

const NavActions = styled.div`
  display: flex;
  gap: 12px;
  align-items: center;
`;

const ThemeToggle = styled.button`
  background: none;
  border: 1px solid #ddd;
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 16px;
  
  &:hover {
    background-color: #f8f9fa;
  }
`;

const UserInfo = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background-color: #f8f9fa;
  border-radius: 20px;
  font-size: 14px;
`;

const Navbar = () => {
  const location = useLocation();
  const dispatch = useDispatch();
  const { user, loading } = useSelector(state => state.user);
  const { theme } = useSelector(state => state.ui);

  const handleModalDemo = () => {
    dispatch(openModal({
      type: 'confirmation',
      title: 'Demo Modal',
      props: {
        message: 'This is a demonstration of the conditional modal component!',
        onConfirm: () => {
          console.log('Confirmed!');
        }
      }
    }));
  };

  const handleFormModal = () => {
    dispatch(openModal({
      type: 'form',
      title: 'Contact Form',
      props: {
        fields: [
          { name: 'name', label: 'Name', required: true },
          { name: 'email', label: 'Email', type: 'email', required: true },
          { name: 'message', label: 'Message', type: 'textarea' }
        ],
        onSubmit: (formData) => {
          console.log('Form submitted:', formData);
        }
      }
    }));
  };

  return (
    <Nav>
      <NavContainer>
        <Logo to="/">ResumeBuilder</Logo>
        
        <NavLinks>
          <NavLink to="/" active={location.pathname === '/'}>
            Dashboard
          </NavLink>
          <NavLink to="/resume-builder" active={location.pathname === '/resume-builder'}>
            Resume Builder
          </NavLink>
          <NavLink to="/event" active={location.pathname === '/event'}>
            Diwali Event
          </NavLink>
        </NavLinks>
        
        <NavActions>
          <button 
            className="btn btn-secondary"
            onClick={handleModalDemo}
          >
            Demo Modal
          </button>
          
          <button 
            className="btn btn-primary"
            onClick={handleFormModal}
          >
            Contact Form
          </button>
          
          <ThemeToggle onClick={() => dispatch(toggleTheme())}>
            {theme === 'light' ? '🌙' : '☀️'}
          </ThemeToggle>
          
          {loading ? (
            <div>Loading...</div>
          ) : user ? (
            <UserInfo>
              <span>👤 {user.name}</span>
              <span>({user.subscription})</span>
            </UserInfo>
          ) : (
            <button className="btn btn-primary">Login</button>
          )}
        </NavActions>
      </NavContainer>
    </Nav>
  );
};

export default Navbar;
