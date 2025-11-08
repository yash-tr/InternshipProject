import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import apiClient from '../../api/apiClient';

// Async thunks
export const fetchPolicy = createAsyncThunk(
  'policy/fetchPolicy',
  async () => {
    const response = await apiClient.getPolicy();
    if (response.success) {
      return response.data;
    }
    throw new Error(response.error || 'Failed to fetch policy');
  }
);

export const checkAcknowledgment = createAsyncThunk(
  'policy/checkAcknowledgment',
  async () => {
    const response = await apiClient.checkPolicyAcknowledgment();
    if (response.success) {
      return response.data;
    }
    throw new Error(response.error || 'Failed to check acknowledgment');
  }
);

export const acknowledgePolicy = createAsyncThunk(
  'policy/acknowledgePolicy',
  async (policyId) => {
    const response = await apiClient.acknowledgePolicy(policyId);
    if (response.success) {
      return response.data;
    }
    throw new Error(response.error || 'Failed to acknowledge policy');
  }
);

const policySlice = createSlice({
  name: 'policy',
  initialState: {
    policy: null,
    requiresAcknowledgment: false,
    userAcknowledged: false,
    isOpen: false,
    loading: false,
    error: null
  },
  reducers: {
    openPolicyModal: (state) => {
      state.isOpen = true;
    },
    closePolicyModal: (state) => {
      state.isOpen = false;
    },
    clearError: (state) => {
      state.error = null;
    }
  },
  extraReducers: (builder) => {
    builder
      // Fetch policy
      .addCase(fetchPolicy.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchPolicy.fulfilled, (state, action) => {
        state.loading = false;
        state.policy = action.payload.policy;
        state.userAcknowledged = action.payload.user_acknowledged;
        if (action.payload.policy.requires_acknowledgment && !action.payload.user_acknowledged) {
          state.isOpen = true;
        }
      })
      .addCase(fetchPolicy.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message;
      })
      // Check acknowledgment
      .addCase(checkAcknowledgment.fulfilled, (state, action) => {
        state.requiresAcknowledgment = action.payload.requires_acknowledgment;
        if (action.payload.requires_acknowledgment) {
          state.isOpen = true;
        }
      })
      // Acknowledge policy
      .addCase(acknowledgePolicy.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(acknowledgePolicy.fulfilled, (state, action) => {
        state.loading = false;
        state.userAcknowledged = true;
        state.isOpen = false;
      })
      .addCase(acknowledgePolicy.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message;
      });
  }
});

export const { openPolicyModal, closePolicyModal, clearError } = policySlice.actions;
export default policySlice.reducer;

