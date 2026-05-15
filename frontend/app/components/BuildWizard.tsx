"use client";

import { useState } from "react";
import { CLASSES, WEAPONS, ClassData, AscendancyData, WeaponData } from "./wizardData";
import styles from "./wizard.module.css";

type Step = "class" | "ascendancy" | "weapon" | "skill";

interface WizardSelections {
  class: ClassData | null;
  ascendancy: AscendancyData | null;
  weapon: WeaponData | null;
  skill: string | null;
}

interface BuildWizardProps {
  onComplete: (selections: {
    skill: string;
    ascendancy: string;
    className: string;
    weapon: string;
  }) => void;
  onBack?: () => void;
}

const STEP_ORDER: Step[] = ["class", "ascendancy", "weapon", "skill"];
const STEP_LABELS: Record<Step, string> = {
  class: "Choose Class",
  ascendancy: "Choose Ascendancy",
  weapon: "Choose Weapon",
  skill: "Choose Skill",
};

export default function BuildWizard({ onComplete, onBack }: BuildWizardProps) {
  const [currentStep, setCurrentStep] = useState<Step>("class");
  const [selections, setSelections] = useState<WizardSelections>({
    class: null,
    ascendancy: null,
    weapon: null,
    skill: null,
  });

  const currentStepIndex = STEP_ORDER.indexOf(currentStep);

  const handleClassSelect = (cls: ClassData) => {
    setSelections({ class: cls, ascendancy: null, weapon: null, skill: null });
    setCurrentStep("ascendancy");
  };

  const handleAscendancySelect = (asc: AscendancyData) => {
    setSelections((prev) => ({ ...prev, ascendancy: asc }));
    setCurrentStep("weapon");
  };

  const handleWeaponSelect = (weapon: WeaponData) => {
    setSelections((prev) => ({ ...prev, weapon, skill: null }));
    setCurrentStep("skill");
  };

  const handleSkillSelect = (skill: string) => {
    setSelections((prev) => ({ ...prev, skill }));
  };

  const handleGenerate = () => {
    const { class: cls, ascendancy, weapon, skill } = selections;
    if (!cls || !ascendancy || !weapon || !skill) return;
    onComplete({
      skill,
      ascendancy: ascendancy.name,
      className: cls.name,
      weapon: weapon.name,
    });
  };

  const handleBack = () => {
    if (currentStepIndex === 0) {
      onBack?.();
    } else {
      const prevStep = STEP_ORDER[currentStepIndex - 1];
      goToStep(prevStep);
    }
  };

  const goToStep = (step: Step) => {
    const targetIndex = STEP_ORDER.indexOf(step);
    if (targetIndex < currentStepIndex) {
      setCurrentStep(step);
      // Clear selections after the target step
      if (step === "class") setSelections({ class: null, ascendancy: null, weapon: null, skill: null });
      if (step === "ascendancy") setSelections((prev) => ({ ...prev, ascendancy: null, weapon: null, skill: null }));
      if (step === "weapon") setSelections((prev) => ({ ...prev, weapon: null, skill: null }));
      if (step === "skill") setSelections((prev) => ({ ...prev, skill: null }));
    }
  };

  return (
    <div className={styles.wizard}>
      <button className={styles.backBtn} onClick={handleBack}>
        ← Back
      </button>
      {/* Progress breadcrumb */}
      <div className={styles.breadcrumb}>
        {STEP_ORDER.map((step, i) => {
          const isComplete = i < currentStepIndex;
          const isCurrent = step === currentStep;
          const isClickable = isComplete;
          return (
            <div key={step} className={styles.breadcrumbItem}>
              <button
                className={`${styles.breadcrumbStep} ${isCurrent ? styles.breadcrumbCurrent : ""} ${isComplete ? styles.breadcrumbDone : ""}`}
                onClick={() => isClickable && goToStep(step)}
                disabled={!isClickable && !isCurrent}
              >
                <span className={styles.breadcrumbNum}>{i + 1}</span>
                <span className={styles.breadcrumbLabel}>{STEP_LABELS[step]}</span>
              </button>
              {i < STEP_ORDER.length - 1 && (
                <span className={`${styles.breadcrumbArrow} ${isComplete ? styles.breadcrumbArrowDone : ""}`}>›</span>
              )}
            </div>
          );
        })}
      </div>

      {/* Selection summary */}
      {(selections.class || selections.ascendancy || selections.weapon) && (
        <div className={styles.summary}>
          {selections.class && <span className={styles.summaryTag}>{selections.class.name}</span>}
          {selections.ascendancy && <><span className={styles.summarySep}>·</span><span className={styles.summaryTag}>{selections.ascendancy.name}</span></>}
          {selections.weapon && <><span className={styles.summarySep}>·</span><span className={styles.summaryTag}>{selections.weapon.name}</span></>}
          {selections.skill && <><span className={styles.summarySep}>·</span><span className={styles.summaryTag}>{selections.skill}</span></>}
        </div>
      )}

      {/* Step content */}
      <div className={styles.stepContent}>

        {/* Step 1: Class */}
        {currentStep === "class" && (
          <div className={styles.step}>
            <h2 className={styles.stepTitle}>Pick Your Class</h2>
            <p className={styles.stepSubtitle}>Your class determines available ascendancies</p>
            <div className={styles.cardGrid}>
              {CLASSES.map((cls) => (
                <button
                  key={cls.id}
                  className={styles.selectionCard}
                  onClick={() => handleClassSelect(cls)}
                >
                  <div className={styles.cardImage}>
                    <img
                      src={cls.image}
                      alt={cls.name}
                      className={styles.cardImg}
                      onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                    />
                    <div className={styles.cardPlaceholder}>
                      <span className={styles.placeholderIcon}>⚔</span>
                    </div>
                  </div>
                  <span className={styles.cardLabel}>{cls.name}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Step 2: Ascendancy */}
        {currentStep === "ascendancy" && selections.class && (
          <div className={styles.step}>
            <h2 className={styles.stepTitle}>Pick Your Ascendancy</h2>
            <p className={styles.stepSubtitle}>{selections.class.name} ascendancies</p>
            <div className={styles.cardGrid}>
              {selections.class.ascendancies.map((asc) => (
                <button
                  key={asc.id}
                  className={styles.selectionCard}
                  onClick={() => handleAscendancySelect(asc)}
                >
                  <div className={styles.cardImage}>
                    <img
                      src={asc.image}
                      alt={asc.name}
                      className={styles.cardImg}
                      onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                    />
                    <div className={styles.cardPlaceholder}>
                      <span className={styles.placeholderIcon}>✦</span>
                    </div>
                  </div>
                  <span className={styles.cardLabel}>{asc.name}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Step 3: Weapon */}
        {currentStep === "weapon" && (
          <div className={styles.step}>
            <h2 className={styles.stepTitle}>Pick Your Weapon</h2>
            <p className={styles.stepSubtitle}>All weapons are available to every class</p>
            <div className={styles.cardGrid}>
              {WEAPONS.map((weapon) => (
                <button
                  key={weapon.id}
                  className={styles.selectionCard}
                  onClick={() => handleWeaponSelect(weapon)}
                >
                  <div className={styles.cardImage}>
                    <img
                      src={weapon.image}
                      alt={weapon.name}
                      className={styles.cardImg}
                      onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                    />
                    <div className={styles.cardPlaceholder}>
                      <span className={styles.placeholderIcon}>🗡</span>
                    </div>
                  </div>
                  <span className={styles.cardLabel}>{weapon.name}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Step 4: Skill */}
        {currentStep === "skill" && selections.weapon && (
          <div className={styles.step}>
            <h2 className={styles.stepTitle}>Pick Your Skill</h2>
            <p className={styles.stepSubtitle}>Skills available for {selections.weapon.name}</p>
            <div className={styles.skillGrid}>
              {selections.weapon.skills.map((skill) => (
                <button
                  key={skill}
                  className={`${styles.skillCard} ${selections.skill === skill ? styles.skillCardSelected : ""}`}
                  onClick={() => handleSkillSelect(skill)}
                >
                  <span className={styles.skillBullet}>▸</span>
                  {skill}
                </button>
              ))}
            </div>

            {selections.skill && (
              <div className={styles.generateWrapper}>
                <button className={styles.generateBtn} onClick={handleGenerate}>
                  ⚡ Generate Build Guide
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
