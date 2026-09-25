"use client";

import { Modal } from "@/components/ui/Modal";
import { buttonClass } from "@/components/ui/Button";
import { useCallback, useState, type ReactNode } from "react";

type ConfirmOptions = {
  title: string;
  body?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  
  input?: { label: string; placeholder?: string; initial?: string };
};

type Pending = {
  options: ConfirmOptions;
  resolve: (value: string | null) => void;
};

export function useConfirm() {
  const [pending, setPending] = useState<Pending | null>(null);
  const [value, setValue] = useState("");

  const open = useCallback((options: ConfirmOptions) => {
    setValue(options.input?.initial ?? "");
    return new Promise<string | null>((resolve) => setPending({ options, resolve }));
  }, []);

  const confirm = useCallback(
    async (options: ConfirmOptions) => (await open({ ...options, input: undefined })) !== null,
    [open],
  );

  const prompt = useCallback(
    (options: ConfirmOptions & { input: NonNullable<ConfirmOptions["input"]> }) => open(options),
    [open],
  );

  const settle = (result: string | null) => {
    pending?.resolve(result);
    setPending(null);
  };

  const options = pending?.options;
  const dialog = (
    <Modal
      open={Boolean(pending)}
      onClose={() => settle(null)}
      tone={options?.destructive ? "danger" : "brand"}
      mark={options?.destructive ? "trash" : "check"}
      title={options?.title ?? ""}
      footer={
        <>
          <button type="button" className={buttonClass({ variant: "outline" })} onClick={() => settle(null)}>
            {options?.cancelLabel ?? "Cancel"}
          </button>
          <button
            type="button"
            className={buttonClass({ variant: options?.destructive ? "destructive" : "primary" })}
            onClick={() => settle(options?.input ? value : "")}
          >
            {options?.confirmLabel ?? "Confirm"}
          </button>
        </>
      }
    >
      {options?.body ? <div className="tb-type-body">{options.body}</div> : null}
      {options?.input ? (
        <label className="mt-3 flex flex-col gap-1.5">
          <span className="tb-field-label">{options.input.label}</span>
          <textarea
            value={value}
            placeholder={options.input.placeholder}
            onChange={(e) => setValue(e.target.value)}
            rows={3}
          />
        </label>
      ) : null}
    </Modal>
  );

  return { confirm, prompt, dialog };
}
