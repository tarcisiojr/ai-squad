"""Testes para validação de nome de time."""

import click
import pytest

from ai_squad.cli.team_manager import validate_team_name


class TestValidateTeamName:
    """Testes para validate_team_name — prevenção de path traversal e injection."""

    def test_nome_simples_valido(self):
        """Aceita nome alfanumérico simples."""
        validate_team_name("backend")

    def test_nome_com_hifen_valido(self):
        """Aceita nome com hífen."""
        validate_team_name("meu-time")

    def test_nome_com_underscore_valido(self):
        """Aceita nome com underscore."""
        validate_team_name("meu_time")

    def test_nome_com_numeros_valido(self):
        """Aceita nome com números."""
        validate_team_name("time42")

    def test_nome_comecando_com_numero_valido(self):
        """Aceita nome começando com número."""
        validate_team_name("1time")

    def test_nome_misto_valido(self):
        """Aceita nome com letras, números, hífen e underscore."""
        validate_team_name("My-Team_01")

    def test_nome_64_caracteres_valido(self):
        """Aceita nome com exatamente 64 caracteres (máximo)."""
        validate_team_name("a" * 64)

    def test_nome_vazio_invalido(self):
        """Rejeita nome vazio."""
        with pytest.raises(click.BadParameter, match="Nome inválido"):
            validate_team_name("")

    def test_nome_65_caracteres_invalido(self):
        """Rejeita nome com mais de 64 caracteres."""
        with pytest.raises(click.BadParameter, match="Nome inválido"):
            validate_team_name("a" * 65)

    def test_path_traversal_invalido(self):
        """Rejeita tentativa de path traversal."""
        with pytest.raises(click.BadParameter, match="Nome inválido"):
            validate_team_name("../../../etc/passwd")

    def test_path_traversal_ponto_duplo(self):
        """Rejeita nome com '..'."""
        with pytest.raises(click.BadParameter, match="Nome inválido"):
            validate_team_name("..")

    def test_nome_com_barra_invalido(self):
        """Rejeita nome com barra (path injection)."""
        with pytest.raises(click.BadParameter, match="Nome inválido"):
            validate_team_name("time/malicioso")

    def test_nome_com_espaco_invalido(self):
        """Rejeita nome com espaço."""
        with pytest.raises(click.BadParameter, match="Nome inválido"):
            validate_team_name("meu time")

    def test_nome_com_ponto_invalido(self):
        """Rejeita nome começando com ponto (arquivo oculto)."""
        with pytest.raises(click.BadParameter, match="Nome inválido"):
            validate_team_name(".hidden")

    def test_nome_com_caracteres_especiais_invalido(self):
        """Rejeita nome com caracteres especiais (possível injection)."""
        with pytest.raises(click.BadParameter, match="Nome inválido"):
            validate_team_name("time;rm -rf /")

    def test_nome_comecando_com_hifen_invalido(self):
        """Rejeita nome começando com hífen (possível flag injection)."""
        with pytest.raises(click.BadParameter, match="Nome inválido"):
            validate_team_name("-malicioso")

    def test_nome_comecando_com_underscore_invalido(self):
        """Rejeita nome começando com underscore."""
        with pytest.raises(click.BadParameter, match="Nome inválido"):
            validate_team_name("_interno")

    def test_nome_com_aspas_invalido(self):
        """Rejeita nome com aspas (shell injection)."""
        with pytest.raises(click.BadParameter, match="Nome inválido"):
            validate_team_name('time"malicioso')

    def test_nome_com_dolar_invalido(self):
        """Rejeita nome com $ (variável de shell)."""
        with pytest.raises(click.BadParameter, match="Nome inválido"):
            validate_team_name("time$HOME")

    def test_nome_com_backtick_invalido(self):
        """Rejeita nome com backtick (command substitution)."""
        with pytest.raises(click.BadParameter, match="Nome inválido"):
            validate_team_name("time`whoami`")
