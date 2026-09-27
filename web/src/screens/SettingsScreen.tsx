import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button, Card, Notice } from "../components/ui";
import { LANGUAGES, setLanguage, type LanguageCode } from "../i18n";
import { getIdentity, setIdentity, type Identity } from "../lib/identity";

/**
 * Everything the citizen can change, and the one thing they can erase.
 *
 * "Clear my data on this device" is deliberately honest about its limits: it
 * empties this browser, and it cannot reach assessments already submitted,
 * because those carry no name and there is no way to work backwards from them
 * to a person. Claiming otherwise would be the easy lie.
 */
export function SettingsScreen({
  onSaved,
  onBack,
}: {
  onSaved: (identity: Identity) => void;
  onBack: () => void;
}) {
  const { t, i18n } = useTranslation();
  const current = getIdentity();
  const [nickname, setNickname] = useState(current.nickname);
  const [team, setTeam] = useState(current.team);
  const [saved, setSaved] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);

  const save = () => {
    onSaved(setIdentity(nickname, team));
    setSaved(true);
  };

  const clearEverything = () => {
    try {
      localStorage.clear();
    } catch {
      // Storage blocked. Nothing was stored either, so nothing to clear.
    }
    window.location.reload();
  };

  return (
    <div className="flex flex-col gap-5">
      <header>
        <button
          type="button"
          onClick={onBack}
          className="tap mb-2 text-sm font-semibold text-brand"
        >
          ← {t("common.back")}
        </button>
        <h2 className="text-xl font-bold text-ink">{t("settings.title")}</h2>
      </header>

      <Card className="flex flex-col gap-3">
        <h3 className="font-semibold text-ink">{t("settings.youTitle")}</h3>

        <label className="flex flex-col gap-1">
          <span className="text-sm font-semibold text-muted">
            {t("settings.nickname")}
          </span>
          <input
            value={nickname}
            onChange={(event) => {
              setNickname(event.target.value);
              setSaved(false);
            }}
            maxLength={40}
            className="tap rounded-xl border-2 border-line bg-white px-4 py-3 text-base"
          />
          <span className="text-xs text-muted">{t("settings.nicknameHelp")}</span>
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-sm font-semibold text-muted">
            {t("settings.team")}
          </span>
          <input
            value={team}
            onChange={(event) => {
              setTeam(event.target.value.toUpperCase());
              setSaved(false);
            }}
            maxLength={40}
            className="tap rounded-xl border-2 border-line bg-white px-4 py-3 text-base"
          />
          <span className="text-xs text-muted">{t("settings.teamHelp")}</span>
        </label>

        <Button onClick={save}>{t("settings.save")}</Button>
        {saved ? <Notice tone="good">{t("settings.saved")}</Notice> : null}
      </Card>

      <Card className="flex flex-col gap-2">
        <h3 className="font-semibold text-ink">{t("app.language")}</h3>
        <label className="sr-only" htmlFor="settings-lang">
          {t("app.language")}
        </label>
        <select
          id="settings-lang"
          value={i18n.language}
          onChange={(event) => setLanguage(event.target.value as LanguageCode)}
          className="tap rounded-xl border-2 border-line bg-white px-4 py-3 text-base"
        >
          {LANGUAGES.map((language) => (
            <option key={language.code} value={language.code}>
              {language.label}
              {language.city ? ` · ${language.city}` : ""}
            </option>
          ))}
        </select>
        {i18n.language !== "en" ? (
          <p className="text-xs text-muted">{t("app.translationWarning")}</p>
        ) : null}
      </Card>

      <Card className="flex flex-col gap-3">
        <h3 className="font-semibold text-ink">{t("settings.clearTitle")}</h3>
        <p className="text-sm text-muted">{t("settings.clearBody")}</p>
        <p className="text-sm text-muted">{t("settings.clearLimit")}</p>

        {confirmClear ? (
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setConfirmClear(false)}>
              {t("common.back")}
            </Button>
            <Button variant="danger" full onClick={clearEverything}>
              {t("settings.clearConfirm")}
            </Button>
          </div>
        ) : (
          <Button variant="danger" onClick={() => setConfirmClear(true)}>
            {t("settings.clear")}
          </Button>
        )}
      </Card>

      <p className="text-xs text-muted">
        <a className="underline" href="https://github.com/Mitalimehta02/streamlens/blob/main/docs/privacy.md" target="_blank" rel="noreferrer">
          {t("settings.privacyLink")}
        </a>
      </p>
    </div>
  );
}
