import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import apiClient from '../../api/apiClient';

// Async thunks
export const fetchJobs = createAsyncThunk(
  'jobs/fetchJobs',
  async (params = {}) => {
    const response = await apiClient.getJobs(params);
    if (response.success) {
      return response.data;
    }
    throw new Error(response.error || 'Failed to fetch jobs');
  }
);

export const saveJob = createAsyncThunk(
  'jobs/saveJob',
  async (jobId) => {
    const response = await apiClient.saveJob(jobId);
    if (response.success) {
      return { jobId };
    }
    throw new Error(response.error || 'Failed to save job');
  }
);

export const unsaveJob = createAsyncThunk(
  'jobs/unsaveJob',
  async (jobId) => {
    const response = await apiClient.unsaveJob(jobId);
    if (response.success) {
      return { jobId };
    }
    throw new Error(response.error || 'Failed to unsave job');
  }
);

export const fetchSavedJobs = createAsyncThunk(
  'jobs/fetchSavedJobs',
  async () => {
    const response = await apiClient.getSavedJobs();
    if (response.success) {
      return response.data;
    }
    throw new Error(response.error || 'Failed to fetch saved jobs');
  }
);

const jobsSlice = createSlice({
  name: 'jobs',
  initialState: {
    jobs: [],
    savedJobs: [],
    loading: false,
    savingJobId: null,
    error: null
  },
  reducers: {
    clearError: (state) => {
      state.error = null;
    }
  },
  extraReducers: (builder) => {
    builder
      // Fetch jobs
      .addCase(fetchJobs.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchJobs.fulfilled, (state, action) => {
        state.loading = false;
        state.jobs = action.payload.jobs || [];
      })
      .addCase(fetchJobs.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message;
      })
      // Save job
      .addCase(saveJob.pending, (state, action) => {
        state.savingJobId = action.meta.arg;
      })
      .addCase(saveJob.fulfilled, (state, action) => {
        state.savingJobId = null;
        if (!state.savedJobs.includes(action.payload.jobId)) {
          state.savedJobs.push(action.payload.jobId);
        }
      })
      .addCase(saveJob.rejected, (state, action) => {
        state.savingJobId = null;
        state.error = action.error.message;
      })
      // Unsave job
      .addCase(unsaveJob.pending, (state, action) => {
        state.savingJobId = action.meta.arg;
      })
      .addCase(unsaveJob.fulfilled, (state, action) => {
        state.savingJobId = null;
        state.savedJobs = state.savedJobs.filter(id => id !== action.payload.jobId);
      })
      .addCase(unsaveJob.rejected, (state, action) => {
        state.savingJobId = null;
        state.error = action.error.message;
      })
      // Fetch saved jobs
      .addCase(fetchSavedJobs.fulfilled, (state, action) => {
        state.savedJobs = action.payload.job_ids || [];
      });
  }
});

export const { clearError } = jobsSlice.actions;
export default jobsSlice.reducer;

