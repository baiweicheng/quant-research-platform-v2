import * as Dialog from "@radix-ui/react-dialog";
import * as Tooltip from "@radix-ui/react-tooltip";
import { ArrowUpRight, Check, CircleHelp, FlaskConical, X } from "lucide-react";
import type { ReactNode } from "react";
import { percent, points } from "./api";
import type { Metrics, Period } from "./types";
import { PERIODS } from "./types";

export function Badge({
  children,
  tone = "",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
export function Help({ text }: { text: string }) {
  return (
    <Tooltip.Provider delayDuration={150}>
      <Tooltip.Root>
        <Tooltip.Trigger className="help" aria-label={text}>
          <CircleHelp size={14} />
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content className="tooltip" sideOffset={8}>
            {text}
            <Tooltip.Arrow />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  );
}
export function Modal({
  title,
  description,
  open,
  onClose,
  children,
}: {
  title: string;
  description: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={(value) => !value && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="modal-overlay" />
        <Dialog.Content className="modal-content">
          <div className="modal-heading">
            <div>
              <Dialog.Title>{title}</Dialog.Title>
              <Dialog.Description>{description}</Dialog.Description>
            </div>
            <Dialog.Close className="icon-button" aria-label="Close dialog">
              <X size={20} />
            </Dialog.Close>
          </div>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export function Empty({
  title,
  children,
  action,
}: {
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <FlaskConical size={24} />
      </span>
      <h3>{title}</h3>
      <p>{children}</p>
      {action}
    </div>
  );
}
export function Notice({
  children,
  error = false,
}: {
  children: ReactNode;
  error?: boolean;
}) {
  return (
    <div
      className={`notice ${error ? "error" : ""}`}
      role={error ? "alert" : "note"}
    >
      {children}
    </div>
  );
}
export function PeriodPicker({
  value,
  onChange,
}: {
  value: Period;
  onChange: (p: Period) => void;
}) {
  return (
    <div className="periods" role="group" aria-label="Performance period">
      {PERIODS.map((p) => (
        <button key={p} aria-pressed={p === value} onClick={() => onChange(p)}>
          {p}
        </button>
      ))}
    </div>
  );
}
export function MetricStrip({
  metrics,
  account = false,
}: {
  metrics?: Metrics;
  account?: boolean;
}) {
  return (
    <div className="metrics">
      <div>
        <span>
          {account ? "Account return" : "Strategy return"}
          <Help text="Change in portfolio value over the selected period, including modeled costs and dividend entitlements." />
        </span>
        <strong
          className={
            metrics?.return != null && metrics.return > 0 ? "positive" : ""
          }
        >
          {percent(metrics?.return, true)}
        </strong>
        <small>
          {account
            ? "Available after paper trading begins"
            : "After modeled costs"}
        </small>
      </div>
      <div>
        <span>
          Compared with SPY
          <Help text="Strategy return minus SPY return, in percentage points, over the same displayed dates. SPY data must cover the whole period." />
        </span>
        <strong>{points(metrics?.difference)}</strong>
        <small>
          {account
            ? "No account history yet"
            : `SPY ${percent(metrics?.benchmark_return, true)}`}
        </small>
      </div>
      <div>
        <span>
          Largest decline
          <Help text="The largest fall from a prior peak within this displayed period. This is historical drawdown, not a limit on future losses." />
        </span>
        <strong>{percent(metrics?.drawdown)}</strong>
        <small>From a peak in this period</small>
      </div>
    </div>
  );
}
export function Step({
  complete,
  title,
  detail,
}: {
  complete: boolean;
  title: string;
  detail: string;
}) {
  return (
    <div className="step">
      <span className={`step-check ${complete ? "done" : ""}`}>
        {complete ? <Check size={13} /> : <span />}
      </span>
      <div>
        <strong>{title}</strong>
        <p>{detail}</p>
      </div>
    </div>
  );
}
export function TextLink({
  children,
  onClick,
}: {
  children: ReactNode;
  onClick: () => void;
}) {
  return (
    <button className="text-link" onClick={onClick}>
      {children}
      <ArrowUpRight size={15} />
    </button>
  );
}
