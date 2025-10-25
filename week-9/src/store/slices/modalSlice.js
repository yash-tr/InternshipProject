import { createSlice } from '@reduxjs/toolkit';

const initialState = {
  isOpen: false,
  modalType: null,
  modalProps: {},
  content: null,
  layout: 'default',
};

const modalSlice = createSlice({
  name: 'modal',
  initialState,
  reducers: {
    openModal: (state, action) => {
      const { type, props = {}, content, layout = 'default' } = action.payload;
      state.isOpen = true;
      state.modalType = type;
      state.modalProps = props;
      state.content = content;
      state.layout = layout;
    },
    closeModal: (state) => {
      state.isOpen = false;
      state.modalType = null;
      state.modalProps = {};
      state.content = null;
      state.layout = 'default';
    },
    updateModalContent: (state, action) => {
      state.content = action.payload;
    },
    setModalLayout: (state, action) => {
      state.layout = action.payload;
    },
  },
});

export const {
  openModal,
  closeModal,
  updateModalContent,
  setModalLayout,
} = modalSlice.actions;

export default modalSlice.reducer;
