import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import apiClient from '../../api/apiClient';

// Async thunks
export const fetchFlags = createAsyncThunk(
  'flagging/fetchFlags',
  async (params = {}) => {
    const response = await apiClient.getFlags(params);
    if (response.success) {
      return response.data;
    }
    throw new Error(response.error || 'Failed to fetch flags');
  }
);

export const submitFlag = createAsyncThunk(
  'flagging/submitFlag',
  async (flagData) => {
    const response = await apiClient.createFlag(flagData);
    if (response.success) {
      return response.data;
    }
    throw new Error(response.error || 'Failed to submit flag');
  }
);

export const resolveFlag = createAsyncThunk(
  'flagging/resolveFlag',
  async ({ flagId, resolutionNotes }) => {
    const response = await apiClient.resolveFlag(flagId, resolutionNotes);
    if (response.success) {
      return response.data;
    }
    throw new Error(response.error || 'Failed to resolve flag');
  }
);

const flaggingSlice = createSlice({
  name: 'flagging',
  initialState: {
    flags: [],
    isOpen: false,
    entityType: null,
    entityId: null,
    loading: false,
    error: null,
    statistics: null
  },
  reducers: {
    openFlaggingModal: (state, action) => {
      state.isOpen = true;
      state.entityType = action.payload.entityType;
      state.entityId = action.payload.entityId;
    },
    closeFlaggingModal: (state) => {
      state.isOpen = false;
      state.entityType = null;
      state.entityId = null;
    },
    clearError: (state) => {
      state.error = null;
    }
  },
  extraReducers: (builder) => {
    builder
      // Fetch flags
      .addCase(fetchFlags.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchFlags.fulfilled, (state, action) => {
        state.loading = false;
        state.flags = action.payload.flags || [];
      })
      .addCase(fetchFlags.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message;
      })
      // Submit flag
      .addCase(submitFlag.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(submitFlag.fulfilled, (state, action) => {
        state.loading = false;
        state.flags.unshift(action.payload.flag);
        state.isOpen = false;
      })
      .addCase(submitFlag.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message;
      })
      // Resolve flag
      .addCase(resolveFlag.fulfilled, (state, action) => {
        const index = state.flags.findIndex(f => f.id === action.payload.flag.id);
        if (index !== -1) {
          state.flags[index] = action.payload.flag;
        }
      });
  }
});

export const { openFlaggingModal, closeFlaggingModal, clearError } = flaggingSlice.actions;
export default flaggingSlice.reducer;

