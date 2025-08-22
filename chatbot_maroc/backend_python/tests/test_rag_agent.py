from unittest.mock import Mock

from src.agents.rag_agent import RAGAgent


def test_rag_agent_execute(mock_rag, sample_state):
    """Test de l'agent RAG"""
    # Setup
    chatbot_mock = Mock()
    agent = RAGAgent(mock_rag, chatbot_mock)

    # Execute
    result = agent.execute(sample_state)

    # Assert
    assert mock_rag.rechercher_tableaux.called
    assert len(result['tableaux_charges']) > 0
    assert chatbot_mock._log.called


def test_valider_donnees_tableau():
    """Test validation des données"""
    agent = RAGAgent(Mock(), Mock())

    # Données valides
    valid_data = {
        'tableau': [['col1', 'col2'], ['val1', 'val2']]
    }
    assert agent._valider_donnees_tableau(valid_data) == True

    # Données invalides
    invalid_data = {'tableau': []}
    assert agent._valider_donnees_tableau(invalid_data) == False

    # Données None
    assert agent._valider_donnees_tableau(None) == False


def test_rag_agent_question_vide(mock_rag, sample_state):
    """Test avec question vide"""
    chatbot_mock = Mock()
    agent = RAGAgent(mock_rag, chatbot_mock)

    # Question vide
    sample_state['question_utilisateur'] = ""

    result = agent.execute(sample_state)

    # Vérifier que l'agent gère l'erreur
    assert len(result['tableaux_charges']) == 0
    assert chatbot_mock._log_error.called


def test_rag_agent_aucun_resultat(sample_state):
    """Test quand RAG ne trouve rien"""
    # Mock RAG qui ne trouve rien
    mock_rag = Mock()
    mock_rag.rechercher_tableaux.return_value = {'tableaux': []}

    chatbot_mock = Mock()
    agent = RAGAgent(mock_rag, chatbot_mock)

    result = agent.execute(sample_state)

    assert len(result['tableaux_charges']) == 0
    assert len(result['tableaux_pertinents']) == 0