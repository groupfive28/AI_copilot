import { PIPELINE_STAGES } from "./constants.js";

export default function PipelineStepper({ stage }) {
  if (!stage) return null;

  const currentIndex = PIPELINE_STAGES.findIndex((s) => s.value === stage);
  const isFinished = stage === "done";

  return (
    <div className="ops-pipeline-stepper">
      {PIPELINE_STAGES.map((step, index) => {
        const isDone = index < currentIndex || isFinished;
        const isCurrent = index === currentIndex && !isFinished;
        const className = ["ops-pipeline-step", isDone && "is-done", isCurrent && "is-current"]
          .filter(Boolean)
          .join(" ");
        return (
          <div key={step.value} className={className}>
            <span className="ops-pipeline-step-dot" />
            <span className="ops-pipeline-step-label">{step.label}</span>
          </div>
        );
      })}
    </div>
  );
}
