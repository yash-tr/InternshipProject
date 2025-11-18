import { useEffect, useState } from "react";
import { toastService } from "../services/toastService";
import "./ToastContainer.css";

export function ToastContainer() {
  const [toasts, setToasts] = useState([]);

  useEffect(() => {
    const unsubscribe = toastService.subscribe((toast) => {
      const id = crypto.randomUUID();
      setToasts((current) => [...current, { ...toast, id }]);
      setTimeout(() => {
        setToasts((current) => current.filter((t) => t.id !== id));
      }, 4000);
    });
    return unsubscribe;
  }, []);

  return (
    <div className="toast-container">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast toast-${toast.type}`}>
          {toast.message}
        </div>
      ))}
    </div>
  );
}

