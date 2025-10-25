import { configureStore } from '@reduxjs/toolkit';
import uiReducer from './slices/uiSlice';
import userReducer from './slices/userSlice';
import resumeReducer from './slices/resumeSlice';
import modalReducer from './slices/modalSlice';

export const store = configureStore({
  reducer: {
    ui: uiReducer,
    user: userReducer,
    resume: resumeReducer,
    modal: modalReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        ignoredActions: ['persist/PERSIST'],
      },
    }),
});
