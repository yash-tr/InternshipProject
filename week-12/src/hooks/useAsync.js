import { useCallback, useEffect, useState } from "react";

export function useAsync(fn, deps = [], { immediate = true } = {}) {
  const [loading, setLoading] = useState(immediate);
  const [error, setError] = useState(null);
  const [value, setValue] = useState(null);

  const execute = useCallback(
    async (...args) => {
      setLoading(true);
      setError(null);
      try {
        const result = await fn(...args);
        setValue(result);
        return result;
      } catch (err) {
        setError(err);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    deps
  );

  useEffect(() => {
    if (immediate) {
      execute();
    }
  }, [execute, immediate]);

  return { execute, loading, error, value };
}

