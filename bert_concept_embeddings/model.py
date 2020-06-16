# +
import tensorflow as tf
# +
import tensorflow as tf

#from keras import regularizers
#from keras.models import Model
# noinspection PyPep8Naming

from keras_transformer.extras import ReusableEmbedding, TiedOutputEmbedding
from keras_transformer.position import TransformerCoordinateEmbedding
from keras_transformer.transformer import TransformerACT, TransformerBlock

from bert_concept_embeddings.custom_layers import EncoderLayer, TimeAttention


# -

# -

def transformer_bert_model(
        max_seq_length: int,
        vocabulary_size: int,
        concept_embedding_size: int,
        d_model: int,
        num_heads: int,
        transformer_dropout: float = 0.1,
        embedding_dropout: float = 0.6,
        l2_reg_penalty: float = 1e-4):
    """
    Builds a BERT-based model (Bidirectional Encoder Representations
    from Transformers) following paper "BERT: Pre-training of Deep
    Bidirectional Transformers for Language Understanding"
    (https://arxiv.org/abs/1810.04805)

    Depending on the value passed with `use_universal_transformer` argument,
    this function applies either an Adaptive Universal Transformer (2018)
    or a vanilla Transformer (2017) to do the job (the original paper uses
    vanilla Transformer).
    """
    concept_ids = tf.keras.layers.Input(shape=(max_seq_length,), dtype='int32', name='concept_ids')

    time_stamps = tf.keras.layers.Input(shape=(max_seq_length,), dtype='int32', name='time_stamps')

    mask = tf.keras.layers.Input(shape=(max_seq_length,), dtype='int32', name='mask')

    time_mask = tf.expand_dims(mask, axis=1)

    concept_mask = tf.expand_dims(time_mask, axis=1)

    l2_regularizer = (tf.keras.regularizers.l2(l2_reg_penalty) if l2_reg_penalty else None)

    embedding_layer = ReusableEmbedding(
        vocabulary_size, concept_embedding_size,
        input_length=max_seq_length,
        name='bpe_embeddings',
        # Regularization is based on paper "A Comparative Study on
        # Regularization Strategies for Embedding-based Neural Networks"
        # https://arxiv.org/pdf/1508.03721.pdf
        embeddings_regularizer=l2_regularizer)

    time_embedding_layer = TimeAttention(vocab_size=vocabulary_size, seq_len=max_seq_length)

    output_layer = TiedOutputEmbedding(
        projection_regularizer=l2_regularizer,
        projection_dropout=embedding_dropout,
        name='concept_prediction_logits')

    output_softmax_layer = tf.keras.layers.Softmax(name='concept_predictions')

    coordinate_embedding_layer = TransformerCoordinateEmbedding(1, name='coordinate_embedding')

    next_step_input, embedding_matrix = embedding_layer(concept_ids)

    # Building a Vanilla Transformer (described in
    # "Attention is all you need", 2017)
    next_step_input = coordinate_embedding_layer(next_step_input, step=0)

    time_attention_logits = time_embedding_layer(concept_ids, time_stamps, time_mask)

    for i in range(d_model):
        next_step_input = (
            EncoderLayer(
                name='transformer' + str(i),
                d_model=d_model,
                num_heads=num_heads, dff=2148)
            (next_step_input, concept_mask, time_attention_logits))

        concept_predictions = output_softmax_layer(
            output_layer([next_step_input, embedding_matrix]))

    model = tf.keras.Model(
        inputs=[concept_ids, time_stamps, mask],
        outputs=[concept_predictions])

    return model