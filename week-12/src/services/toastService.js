const listeners = new Set();

export const toastService = {
  subscribe(listener) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  success(message) {
    this.publish({ type: "success", message });
  },
  error(message) {
    this.publish({ type: "error", message });
  },
  info(message) {
    this.publish({ type: "info", message });
  },
  publish(event) {
    listeners.forEach((listener) => listener(event));
  },
};

