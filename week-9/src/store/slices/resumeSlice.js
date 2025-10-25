import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';

// Async thunk for parsing resume data
export const parseResumeData = createAsyncThunk(
  'resume/parseResumeData',
  async (resumeData, { rejectWithValue }) => {
    try {
      // Simulate parsing API call
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      // Mock parsed data
      return {
        personalInfo: {
          name: resumeData.name || 'John Doe',
          email: resumeData.email || 'john@example.com',
          phone: resumeData.phone || '+1-555-0123',
          location: resumeData.location || 'San Francisco, CA'
        },
        experience: resumeData.experience || [],
        education: resumeData.education || [],
        skills: resumeData.skills || [],
        parsedAt: new Date().toISOString()
      };
    } catch (error) {
      return rejectWithValue(error.message);
    }
  }
);

// Async thunk for generating resume
export const generateResume = createAsyncThunk(
  'resume/generateResume',
  async (resumeData, { rejectWithValue }) => {
    try {
      // Simulate generation API call
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      return {
        id: Date.now(),
        status: 'completed',
        downloadUrl: '/api/resume/download/123',
        generatedAt: new Date().toISOString()
      };
    } catch (error) {
      return rejectWithValue(error.message);
    }
  }
);

const initialState = {
  resumeData: null,
  parsedData: null,
  generatedResumes: [],
  loading: false,
  parsing: false,
  generating: false,
  error: null,
  templates: [
    { id: 1, name: 'Modern Professional', category: 'professional' },
    { id: 2, name: 'Creative Design', category: 'creative' },
    { id: 3, name: 'Minimal Clean', category: 'minimal' }
  ],
  selectedTemplate: null,
};

const resumeSlice = createSlice({
  name: 'resume',
  initialState,
  reducers: {
    setResumeData: (state, action) => {
      state.resumeData = action.payload;
    },
    updateParsedData: (state, action) => {
      state.parsedData = { ...state.parsedData, ...action.payload };
    },
    selectTemplate: (state, action) => {
      state.selectedTemplate = action.payload;
    },
    clearError: (state) => {
      state.error = null;
    },
    resetResume: (state) => {
      state.resumeData = null;
      state.parsedData = null;
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(parseResumeData.pending, (state) => {
        state.parsing = true;
        state.error = null;
      })
      .addCase(parseResumeData.fulfilled, (state, action) => {
        state.parsing = false;
        state.parsedData = action.payload;
      })
      .addCase(parseResumeData.rejected, (state, action) => {
        state.parsing = false;
        state.error = action.payload;
      })
      .addCase(generateResume.pending, (state) => {
        state.generating = true;
        state.error = null;
      })
      .addCase(generateResume.fulfilled, (state, action) => {
        state.generating = false;
        state.generatedResumes.push(action.payload);
      })
      .addCase(generateResume.rejected, (state, action) => {
        state.generating = false;
        state.error = action.payload;
      });
  },
});

export const {
  setResumeData,
  updateParsedData,
  selectTemplate,
  clearError,
  resetResume,
} = resumeSlice.actions;

export default resumeSlice.reducer;
