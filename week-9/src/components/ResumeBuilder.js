import React, { useState, useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { parseResumeData, generateResume, setResumeData, selectTemplate } from '../store/slices/resumeSlice';
import { openModal } from '../store/slices/modalSlice';
import { addNotification } from '../store/slices/uiSlice';
import styled from 'styled-components';

const BuilderContainer = styled.div`
  padding: 24px 0;
`;

const BuilderHeader = styled.div`
  background: white;
  padding: 24px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  margin-bottom: 24px;
  text-align: center;
`;

const BuilderTitle = styled.h1`
  margin: 0 0 16px 0;
  color: #333;
  font-size: 28px;
`;

const BuilderSubtitle = styled.p`
  margin: 0;
  color: #666;
  font-size: 16px;
`;

const BuilderGrid = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  
  @media (max-width: 768px) {
    grid-template-columns: 1fr;
  }
`;

const BuilderSection = styled.div`
  background: white;
  padding: 24px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
`;

const SectionTitle = styled.h3`
  margin: 0 0 20px 0;
  color: #333;
  font-size: 20px;
  display: flex;
  align-items: center;
  gap: 12px;
`;

const FormGroup = styled.div`
  margin-bottom: 20px;
`;

const Label = styled.label`
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: #333;
`;

const Input = styled.input`
  width: 100%;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 16px;
  
  &:focus {
    outline: none;
    border-color: #007bff;
    box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.1);
  }
`;

const TextArea = styled.textarea`
  width: 100%;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 16px;
  min-height: 100px;
  resize: vertical;
  
  &:focus {
    outline: none;
    border-color: #007bff;
    box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.1);
  }
`;

const TemplateGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
`;

const TemplateCard = styled.div`
  border: 2px solid ${props => props.selected ? '#007bff' : '#ddd'};
  border-radius: 8px;
  padding: 16px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:hover {
    border-color: #007bff;
    box-shadow: 0 2px 8px rgba(0, 123, 255, 0.1);
  }
`;

const TemplateName = styled.div`
  font-weight: 600;
  margin-bottom: 8px;
  color: #333;
`;

const TemplateCategory = styled.div`
  font-size: 14px;
  color: #666;
  text-transform: capitalize;
`;

const ParsedDataDisplay = styled.div`
  background: #f8f9fa;
  padding: 16px;
  border-radius: 8px;
  margin-top: 16px;
`;

const ParsedItem = styled.div`
  margin-bottom: 12px;
  padding: 8px 12px;
  background: white;
  border-radius: 6px;
  border-left: 4px solid #007bff;
`;

const ResumeBuilder = () => {
  const dispatch = useDispatch();
  const { 
    resumeData, 
    parsedData, 
    generating, 
    parsing, 
    templates, 
    selectedTemplate,
    generatedResumes 
  } = useSelector(state => state.resume);
  
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    experience: '',
    education: '',
    skills: ''
  });

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleParseResume = () => {
    dispatch(setResumeData(formData));
    dispatch(parseResumeData(formData));
    
    dispatch(addNotification({
      message: 'Resume parsing started with enhanced extraction algorithm!',
      type: 'info'
    }));
  };

  const handleGenerateResume = () => {
    if (!selectedTemplate) {
      dispatch(openModal({
        type: 'info',
        title: 'Template Required',
        props: {
          icon: '⚠️',
          description: 'Please select a template before generating your resume.'
        }
      }));
      return;
    }

    dispatch(generateResume(parsedData));
    
    dispatch(addNotification({
      message: 'Resume generation started with optimized backend processing!',
      type: 'success'
    }));
  };

  const handleTemplateSelect = (template) => {
    dispatch(selectTemplate(template));
  };

  const handleShowParsingDemo = () => {
    dispatch(openModal({
      type: 'info',
      title: 'Enhanced Parsing Flow',
      layout: 'wide',
      props: {
        icon: '🔍',
        description: 'Our new parsing algorithm automatically extracts and normalizes user data for more accurate resume generation. This includes intelligent field detection, skill categorization, and experience formatting.'
      }
    }));
  };

  return (
    <BuilderContainer>
      <BuilderHeader>
        <BuilderTitle>Enhanced Resume Builder</BuilderTitle>
        <BuilderSubtitle>
          Experience our new parsing flow with improved accuracy and faster generation
        </BuilderSubtitle>
      </BuilderHeader>

      <BuilderGrid>
        <BuilderSection>
          <SectionTitle>
            📝 Resume Information
            <button 
              className="btn btn-secondary"
              onClick={handleShowParsingDemo}
              style={{ marginLeft: 'auto', fontSize: '12px', padding: '6px 12px' }}
            >
              Learn More
            </button>
          </SectionTitle>
          
          <FormGroup>
            <Label>Full Name</Label>
            <Input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleInputChange}
              placeholder="Enter your full name"
            />
          </FormGroup>

          <FormGroup>
            <Label>Email</Label>
            <Input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleInputChange}
              placeholder="your.email@example.com"
            />
          </FormGroup>

          <FormGroup>
            <Label>Phone</Label>
            <Input
              type="tel"
              name="phone"
              value={formData.phone}
              onChange={handleInputChange}
              placeholder="+1-555-0123"
            />
          </FormGroup>

          <FormGroup>
            <Label>Work Experience</Label>
            <TextArea
              name="experience"
              value={formData.experience}
              onChange={handleInputChange}
              placeholder="Describe your work experience..."
            />
          </FormGroup>

          <FormGroup>
            <Label>Education</Label>
            <TextArea
              name="education"
              value={formData.education}
              onChange={handleInputChange}
              placeholder="List your educational background..."
            />
          </FormGroup>

          <FormGroup>
            <Label>Skills</Label>
            <TextArea
              name="skills"
              value={formData.skills}
              onChange={handleInputChange}
              placeholder="List your skills (comma-separated)..."
            />
          </FormGroup>

          <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
            <button 
              className="btn btn-primary"
              onClick={handleParseResume}
              disabled={parsing}
            >
              {parsing ? 'Parsing...' : 'Parse Resume Data'}
            </button>
            
            <button 
              className="btn btn-success"
              onClick={handleGenerateResume}
              disabled={generating || !parsedData}
            >
              {generating ? 'Generating...' : 'Generate Resume'}
            </button>
          </div>
        </BuilderSection>

        <BuilderSection>
          <SectionTitle>🎨 Choose Template</SectionTitle>
          
          <TemplateGrid>
            {templates.map(template => (
              <TemplateCard
                key={template.id}
                selected={selectedTemplate?.id === template.id}
                onClick={() => handleTemplateSelect(template)}
              >
                <TemplateName>{template.name}</TemplateName>
                <TemplateCategory>{template.category}</TemplateCategory>
              </TemplateCard>
            ))}
          </TemplateGrid>

          {parsedData && (
            <ParsedDataDisplay>
              <h4>📊 Parsed Data Preview</h4>
              <ParsedItem>
                <strong>Name:</strong> {parsedData.personalInfo?.name}
              </ParsedItem>
              <ParsedItem>
                <strong>Email:</strong> {parsedData.personalInfo?.email}
              </ParsedItem>
              <ParsedItem>
                <strong>Phone:</strong> {parsedData.personalInfo?.phone}
              </ParsedItem>
              <ParsedItem>
                <strong>Location:</strong> {parsedData.personalInfo?.location}
              </ParsedItem>
              <ParsedItem>
                <strong>Parsed At:</strong> {new Date(parsedData.parsedAt).toLocaleString()}
              </ParsedItem>
            </ParsedDataDisplay>
          )}

          {generatedResumes.length > 0 && (
            <div style={{ marginTop: '24px' }}>
              <h4>📄 Generated Resumes</h4>
              {generatedResumes.map((resume, index) => (
                <div key={resume.id} className="card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <strong>Resume #{index + 1}</strong>
                      <div style={{ fontSize: '14px', color: '#666' }}>
                        Status: {resume.status} | Generated: {new Date(resume.generatedAt).toLocaleString()}
                      </div>
                    </div>
                    <button className="btn btn-primary" style={{ fontSize: '12px', padding: '6px 12px' }}>
                      Download
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </BuilderSection>
      </BuilderGrid>
    </BuilderContainer>
  );
};

export default ResumeBuilder;
