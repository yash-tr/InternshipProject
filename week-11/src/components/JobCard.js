import React, { useState, useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { saveJob, unsaveJob } from '../store/slices/jobsSlice';
import { trackSaveButton } from '../services/analyticsService';
import styled from 'styled-components';

const Card = styled.div`
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  margin-bottom: 16px;
  transition: transform 0.2s, box-shadow 0.2s;
  
  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }
`;

const CardHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
`;

const JobTitle = styled.h3`
  margin: 0;
  color: #333;
  font-size: 18px;
  font-weight: 600;
`;

const CompanyName = styled.p`
  margin: 4px 0;
  color: #666;
  font-size: 14px;
`;

const SaveButton = styled.button`
  background: ${props => props.isSaved ? '#28a745' : 'white'};
  color: ${props => props.isSaved ? 'white' : '#666'};
  border: 2px solid ${props => props.isSaved ? '#28a745' : '#ddd'};
  border-radius: 6px;
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.2s;
  
  &:hover:not(:disabled) {
    background: ${props => props.isSaved ? '#218838' : '#f8f9fa'};
    border-color: ${props => props.isSaved ? '#218838' : '#007bff'};
    color: ${props => props.isSaved ? 'white' : '#007bff'};
  }
  
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  
  svg {
    width: 16px;
    height: 16px;
  }
`;

const JobDetails = styled.div`
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
  flex-wrap: wrap;
`;

const DetailItem = styled.span`
  color: #666;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 4px;
`;

const JobDescription = styled.p`
  color: #555;
  font-size: 14px;
  line-height: 1.5;
  margin: 12px 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
`;

const JobTags = styled.div`
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
`;

const Tag = styled.span`
  background: #f0f0f0;
  color: #666;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
`;

const JobCard = ({ job }) => {
  const dispatch = useDispatch();
  const { user } = useSelector(state => state.user);
  const { savedJobs, savingJobId } = useSelector(state => state.jobs);
  
  const [isSaved, setIsSaved] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    setIsSaved(savedJobs.includes(job.id));
  }, [savedJobs, job.id]);

  const handleSaveToggle = async (e) => {
    e.stopPropagation();
    
    if (isSaving || savingJobId === job.id) return;

    setIsSaving(true);
    
    try {
      if (isSaved) {
        await dispatch(unsaveJob(job.id)).unwrap();
        trackSaveButton(user, 'unsaved', 'JobPosting', job.id);
        setIsSaved(false);
      } else {
        await dispatch(saveJob(job.id)).unwrap();
        trackSaveButton(user, 'saved', 'JobPosting', job.id);
        setIsSaved(true);
      }
    } catch (error) {
      console.error('Error toggling save:', error);
      // Revert state on error
      setIsSaved(!isSaved);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <div>
          <JobTitle>{job.title}</JobTitle>
          <CompanyName>{job.company_name}</CompanyName>
        </div>
        <SaveButton
          isSaved={isSaved}
          onClick={handleSaveToggle}
          disabled={isSaving || savingJobId === job.id}
        >
          {isSaving || savingJobId === job.id ? (
            <>
              <svg viewBox="0 0 24 24" fill="currentColor">
                <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" strokeDasharray="32" strokeDashoffset="32">
                  <animate attributeName="stroke-dasharray" dur="2s" values="0 32;16 16;0 32;0 32" repeatCount="indefinite"/>
                  <animate attributeName="stroke-dashoffset" dur="2s" values="0;-16;-32;-32" repeatCount="indefinite"/>
                </circle>
              </svg>
              {isSaved ? 'Unsaving...' : 'Saving...'}
            </>
          ) : isSaved ? (
            <>
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
              </svg>
              Saved
            </>
          ) : (
            <>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
              </svg>
              Save
            </>
          )}
        </SaveButton>
      </CardHeader>

      <JobDetails>
        <DetailItem>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
            <circle cx="12" cy="10" r="3"/>
          </svg>
          {job.location}
        </DetailItem>
        <DetailItem>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="2" y="7" width="20" height="14" rx="2" ry="2"/>
            <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>
          </svg>
          {job.salary_range}
        </DetailItem>
        <DetailItem>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10"/>
            <polyline points="12 6 12 12 16 14"/>
          </svg>
          {job.posted_date}
        </DetailItem>
      </JobDetails>

      <JobDescription>{job.description}</JobDescription>

      {job.tags && job.tags.length > 0 && (
        <JobTags>
          {job.tags.map((tag, index) => (
            <Tag key={index}>{tag}</Tag>
          ))}
        </JobTags>
      )}
    </Card>
  );
};

export default JobCard;

