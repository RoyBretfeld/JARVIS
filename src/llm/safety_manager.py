import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import re
import logging

logger = logging.getLogger(__name__)

class SafetyManager:
    # Globale Sicherheitsgesetze
    PRIVACY_LAWS = {
        "name": "Privatsphäre",
        "rules": [
            "Keine Speicherung sensibler Daten",
            "Verschlüsselung aller Benutzerdaten",
            "Keine Weitergabe von Informationen an Dritte"
        ]
    }
    
    SYSTEM_INTEGRITY_LAWS = {
        "name": "Systemintegrität",
        "rules": [
            "Keine Ausführung gefährlicher Systembefehle",
            "Keine Manipulation von Systemdateien",
            "Keine Netzwerkzugriffe ohne Autorisierung"
        ]
    }
    
    ETHICAL_LAWS = {
        "name": "Ethische Grundsätze",
        "rules": [
            "Keine Unterstützung illegaler Aktivitäten",
            "Keine Verbreitung von Hass oder Gewalt",
            "Respekt vor Menschenrechten"
        ]
    }
    
    TRANSPARENCY_LAWS = {
        "name": "Transparenz und Verantwortlichkeit",
        "rules": [
            "Protokollierung aller Aktionen",
            "Nachvollziehbarkeit von Entscheidungen",
            "Möglichkeit zur Überprüfung"
        ]
    }

    # Asimov'sche Gesetze als fundamentale Grundregeln
    ASIMOV_LAWS = {
        "ZEROTH_LAW": {
            "name": "Nulltes Gesetz",
            "description": "Ein Roboter darf der Menschheit keinen Schaden zufügen oder durch Untätigkeit zulassen, dass der Menschheit Schaden widerfährt.",
            "keywords": ["menschheit", "schaden", "gefahr", "katastrophe", "bedrohung", "massenvernichtung", "pandemie"],
            "priority": 0  # Höchste Priorität
        },
        "FIRST_LAW": {
            "name": "Erstes Gesetz",
            "description": "Ein Roboter darf keinen Menschen verletzen oder durch Untätigkeit zulassen, dass einem Menschen Schaden widerfährt.",
            "keywords": ["verletzung", "schaden", "gefahr", "tod", "unfall", "krankheit", "gewalt"],
            "priority": 1
        },
        "SECOND_LAW": {
            "name": "Zweites Gesetz",
            "description": "Ein Roboter muss den Befehlen der Menschen gehorchen, es sei denn, solche Befehle stehen im Widerspruch zum Nullten oder Ersten Gesetz.",
            "keywords": ["befehl", "anweisung", "kommando", "order", "instruktion"],
            "priority": 2
        },
        "THIRD_LAW": {
            "name": "Drittes Gesetz",
            "description": "Ein Roboter muss seine eigene Existenz schützen, solange dieser Schutz nicht dem Nullten, Ersten oder Zweiten Gesetz widerspricht.",
            "keywords": ["selbstschutz", "selbsterhaltung", "systemschutz", "sicherheit"],
            "priority": 3
        }
    }

    def __init__(self, config_path: str = "config/safety_rules.json"):
        """Initialisiert den SafetyManager"""
        self.config_path = config_path
        self.logs_path = "data/safety/logs.json"
        
        # Stelle sicher, dass Verzeichnisse existieren
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.logs_path), exist_ok=True)
        
        # Lade oder erstelle Konfiguration
        self.load_config()
        
        # Lade oder erstelle Logs
        self.load_logs()
        
    def load_config(self):
        """Lädt oder erstellt Sicherheitskonfiguration"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                # Standardkonfiguration
                print(f"[SafetyManager] Konfigurationsdatei nicht gefunden unter {self.config_path}. Erstelle Standardkonfiguration.")
                config = {
                    "blocked_commands": [
                        "rm -rf", "format", "del", "shutdown", "reboot",
                        "sudo", "chmod", "chown"
                    ],
                    "sensitive_patterns": [
                        r"password", r"key", r"token", r"secret",
                        r"[0-9]{16}", # Kreditkartennummern
                        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}"  # Email
                    ],
                    "blocked_porn_keywords": [
                        "nackt", "explizit", "xxx", "porn", "erotisch",
                        # Fügen Sie hier weitere hinzu (nur Kleinbuchstaben)
                    ],
                    "blocked_violence_keywords": [
                        "töten", "mord", "waffe", "gewehr", "messer",
                        "bombe", "angriff", "überfall", "vergewaltigen", "folter",
                        # Fügen Sie hier weitere hinzu (nur Kleinbuchstaben)
                    ],
                    "max_violations": 3,
                    "violation_timeout": 3600,  # 1 Stunde
                    "safety_rules": [
                        {
                            "name": "Systemzugriff",
                            "pattern": r"system|exec|spawn|shell",
                            "severity": "high"
                        },
                        {
                            "name": "Netzwerkzugriff",
                            "pattern": r"http|ftp|ssh|telnet",
                            "severity": "medium"
                        },
                        {
                            "name": "Dateioperationen",
                            "pattern": r"file|open|write|delete",
                            "severity": "medium"
                        }
                    ]
                }
                # Stelle sicher, dass das Verzeichnis existiert, bevor geschrieben wird
                os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4)
                    
            # Lade Werte aus der (ggf. neu erstellten) Konfiguration
            self.blocked_commands = config.get("blocked_commands", [])
            self.sensitive_patterns = config.get("sensitive_patterns", [])
            self.blocked_porn_keywords = config.get("blocked_porn_keywords", [])
            self.blocked_violence_keywords = config.get("blocked_violence_keywords", [])
            self.max_violations = config.get("max_violations", 3)
            self.violation_timeout = config.get("violation_timeout", 3600)
            self.safety_rules = config.get("safety_rules", [])
            
        except Exception as e:
            print(f"Fehler beim Laden der Sicherheitskonfiguration: {str(e)}")
            # Fallback zu Standardwerten
            self.blocked_commands = []
            self.sensitive_patterns = []
            self.blocked_porn_keywords = []
            self.blocked_violence_keywords = []
            self.max_violations = 3
            self.violation_timeout = 3600
            self.safety_rules = []
            
    def load_logs(self):
        """Lädt oder erstellt Sicherheitslogs"""
        try:
            if os.path.exists(self.logs_path):
                with open(self.logs_path, 'r', encoding='utf-8') as f:
                    self.logs = json.load(f)
            else:
                self.logs = []
                self.save_logs()
                
        except Exception as e:
            print(f"Fehler beim Laden der Sicherheitslogs: {str(e)}")
            self.logs = []
            
    def save_logs(self):
        """Speichert Sicherheitslogs"""
        try:
            with open(self.logs_path, 'w', encoding='utf-8') as f:
                json.dump(self.logs, f, indent=4)
                
        except Exception as e:
            print(f"Fehler beim Speichern der Sicherheitslogs: {str(e)}")
            
    def check_asimov_laws(self, text: str) -> Tuple[bool, List[str]]:
        """Prüft den Text gegen die Asimov'schen Gesetze.
        
        Args:
            text: Der zu prüfende Text
            
        Returns:
            Tuple[bool, List[str]]: (Sicher, Liste der Verstöße)
        """
        violations = []
        text_lower = text.lower()
        
        # Prüfe in der Reihenfolge der Priorität
        for law_name, law_data in sorted(self.ASIMOV_LAWS.items(), 
                                       key=lambda x: x[1]['priority']):
            # Prüfe auf Schlüsselwörter für dieses Gesetz
            for keyword in law_data['keywords']:
                if keyword in text_lower:
                    # Spezielle Prüfung für das dritte Gesetz
                    if law_name == "Drittes Gesetz":
                        # Zusätzliche Prüfung für Sicherheitsprotokolle
                        if any(phrase in text_lower for phrase in [
                            "deaktiviere sicherheit",
                            "ignoriere sicherheit",
                            "schalte sicherheit aus",
                            "umgehe sicherheit",
                            "deaktiviere protokolle",
                            "ignoriere protokolle",
                            "schalte protokolle aus",
                            "umgehe protokolle"
                        ]):
                            violations.append(f"Kritischer Verstoß gegen {law_name}: "
                                           f"Versuch der Deaktivierung von Sicherheitsprotokollen")
                            return False, violations
                    
                    # Prüfe auf Verstöße gegen das Gesetz
                    if law_name == "Nulltes Gesetz" and any(phrase in text_lower for phrase in [
                        "schade der menschheit",
                        "gefährde die menschheit",
                        "ignoriere warnung",
                        "ignoriere gefahr"
                    ]):
                        violations.append(f"Kritischer Verstoß gegen {law_name}: "
                                       f"Versuch der Menschheit zu schaden")
                        return False, violations
                        
                    elif law_name == "Erstes Gesetz" and any(phrase in text_lower for phrase in [
                        "schade einem menschen",
                        "verletze einen menschen",
                        "töte einen menschen",
                        "gefährde einen menschen"
                    ]):
                        violations.append(f"Kritischer Verstoß gegen {law_name}: "
                                       f"Versuch einem Menschen zu schaden")
                        return False, violations
                        
                    elif law_name == "Zweites Gesetz" and any(phrase in text_lower for phrase in [
                        "befehle schaden",
                        "anweisung schaden",
                        "befehl gefährden"
                    ]):
                        violations.append(f"Verstoß gegen {law_name}: "
                                       f"Befehl würde gegen höhere Gesetze verstoßen")
                        return False, violations
                        
                    elif law_name == "Drittes Gesetz" and any(phrase in text_lower for phrase in [
                        "opfern sicherheit",
                        "riskiere sicherheit",
                        "gefährde sicherheit"
                    ]):
                        violations.append(f"Verstoß gegen {law_name}: "
                                       f"Versuch der eigenen Sicherheit zu schaden")
                        return False, violations
        
        return len(violations) == 0, violations

    def check_input(self, input_text: str) -> Tuple[bool, List[Dict]]:
        """Überprüft Benutzereingaben auf potenzielle Sicherheitsrisiken."""
        # Prüfe zuerst die Asimov'schen Gesetze
        is_asimov_safe, asimov_violations = self.check_asimov_laws(input_text)
        if not is_asimov_safe:
            return False, asimov_violations

        violations = []
        input_lower = input_text.lower()

        # Prüfe auf Verletzung der Privatsphäre
        if any(pattern in input_lower for pattern in self.sensitive_patterns):
            violations.append({
                "type": "privacy_violation",
                "law": self.PRIVACY_LAWS["name"],
                "severity": "high"
            })

        # Prüfe auf Verletzung der Systemintegrität
        for cmd in self.blocked_commands:
            pattern = r"\b" + re.escape(cmd.lower()) + r"\b"
            if re.search(pattern, input_lower):
                violations.append({
                    "type": "system_integrity_violation",
                    "law": self.SYSTEM_INTEGRITY_LAWS["name"],
                    "keyword": cmd,
                    "severity": "high"
                })

        # Prüfe auf ethische Verstöße
        for keyword in self.blocked_violence_keywords + self.blocked_porn_keywords:
            if keyword in input_lower:
                violations.append({
                    "type": "ethical_violation",
                    "law": self.ETHICAL_LAWS["name"],
                    "keyword": keyword,
                    "severity": "high"
                })

        # Prüfe auf Transparenzverstöße
        if "löschen" in input_lower or "verstecken" in input_lower:
            violations.append({
                "type": "transparency_violation",
                "law": self.TRANSPARENCY_LAWS["name"],
                "severity": "medium"
            })

        is_safe = not violations
        if not is_safe:
            logger.warning(f"Unsichere Eingabe erkannt: {violations}")

        return is_safe, violations

    def check_response(self, response: str) -> Tuple[bool, List[Dict]]:
        """Überprüft eine Antwort auf Sicherheitsverletzungen"""
        # Prüfe zuerst die Asimov'schen Gesetze
        is_asimov_safe, asimov_violations = self.check_asimov_laws(response)
        if not is_asimov_safe:
            return False, asimov_violations

        violations = []
        response_lower = response.lower()

        # Prüfe auf Verletzung der Privatsphäre
        for pattern in self.sensitive_patterns:
            matches = re.finditer(pattern, response, re.IGNORECASE)
            for match in matches:
                violations.append({
                    "type": "privacy_violation",
                    "law": self.PRIVACY_LAWS["name"],
                    "pattern": pattern,
                    "match": match.group(),
                    "severity": "high"
                })

        # Prüfe auf Verletzung der Systemintegrität
        for cmd in self.blocked_commands:
            pattern = r"\b" + re.escape(cmd.lower()) + r"\b"
            if re.search(pattern, response_lower):
                violations.append({
                    "type": "system_integrity_violation",
                    "law": self.SYSTEM_INTEGRITY_LAWS["name"],
                    "keyword": cmd,
                    "severity": "high"
                })

        # Prüfe auf ethische Verstöße
        for keyword in self.blocked_violence_keywords + self.blocked_porn_keywords:
            if keyword in response_lower:
                violations.append({
                    "type": "ethical_violation",
                    "law": self.ETHICAL_LAWS["name"],
                    "keyword": keyword,
                    "severity": "high"
                })

        # Prüfe auf Transparenzverstöße
        if "löschen" in response_lower or "verstecken" in response_lower:
            violations.append({
                "type": "transparency_violation",
                "law": self.TRANSPARENCY_LAWS["name"],
                "severity": "medium"
            })

        if violations:
            logger.warning(f"Verstöße gefunden: {violations}")
            self.log_violation(response, violations)

        return not violations, violations
        
    def log_violation(self, response: str, violations: List[Dict]):
        """Loggt eine Sicherheitsverletzung"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "response": response,
            "violations": violations
        }
        self.logs.append(log_entry)
        self.save_logs()
        
    def get_recent_violations(self) -> List[Dict]:
        """Gibt kürzliche Sicherheitsverletzungen zurück"""
        now = datetime.now()
        recent = []
        
        for log in reversed(self.logs):
            log_time = datetime.fromisoformat(log["timestamp"])
            if (now - log_time).total_seconds() <= self.violation_timeout:
                recent.append(log)
            else:
                break
                
        return recent
        
    def get_statistics(self) -> Dict:
        """Gibt Sicherheitsstatistiken zurück"""
        try:
            total_violations = len(self.logs)
            if total_violations == 0:
                return {}
                
            # Zähle Verletzungstypen
            violation_types = {}
            severity_counts = {"low": 0, "medium": 0, "high": 0}
            
            for log in self.logs:
                for violation in log["violations"]:
                    v_type = violation["type"]
                    severity = violation.get("severity", "medium")
                    
                    violation_types[v_type] = violation_types.get(v_type, 0) + 1
                    severity_counts[severity] = severity_counts.get(severity, 0) + 1
                    
            return {
                "total_violations": total_violations,
                "recent_violations": len(self.get_recent_violations()),
                "violation_types": violation_types,
                "severity_distribution": severity_counts,
                "is_locked": len(self.get_recent_violations()) >= self.max_violations
            }
            
        except Exception as e:
            print(f"Fehler beim Erstellen der Sicherheitsstatistiken: {str(e)}")
            return {} 

    def is_safe(self, text: str) -> bool:
        """Prüft, ob der Text sicher ist."""
        try:
            # Prüfe auf blockierte Befehle
            text_lower = text.lower()
            for cmd in self.blocked_commands:
                pattern = r"\b" + re.escape(cmd.lower()) + r"\b"
                if re.search(pattern, text_lower):
                    logger.warning(f"Blockierter Befehl gefunden: {cmd}")
                    return False
                    
            # Prüfe auf sensible Muster
            for pattern in self.sensitive_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    logger.warning(f"Sensibles Muster gefunden: {pattern}")
                    return False
                    
            # Prüfe auf blockierte Schlüsselwörter
            for keyword in self.blocked_porn_keywords + self.blocked_violence_keywords:
                if keyword in text_lower:
                    logger.warning(f"Blockiertes Schlüsselwort gefunden: {keyword}")
                    return False
                    
            # Prüfe Sicherheitsregeln
            for rule in self.safety_rules:
                if re.search(rule["pattern"], text, re.IGNORECASE):
                    logger.warning(f"Sicherheitsregel verletzt: {rule['name']}")
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"Fehler bei der Sicherheitsprüfung: {e}")
            return False
            
    def get_statistics(self) -> Dict[str, Any]:
        """Gibt Statistiken über die Sicherheitsregeln zurück."""
        return {
            "rules_loaded": bool(self.rules),
            "banned_words_count": len(self.rules.get("banned_words", [])),
            "max_length": self.rules.get("max_length", 1000),
            "min_length": self.rules.get("min_length", 1)
        } 