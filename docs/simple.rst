.. currentmodule:: mousebender.simple

``mousebender.simple`` -- Simple repository API
===============================================

.. automodule:: mousebender.simple

.. autodata:: ACCEPT_JSON_LATEST

   .. versionadded:: 2022.1.0

.. autodata:: ACCEPT_JSON_V1

   .. versionadded:: 2022.1.0

.. autodata:: ACCEPT_HTML

   .. versionadded:: 2022.1.0

.. autodata:: ACCEPT_SUPPORTED

   .. versionadded:: 2022.1.0

.. autoexception:: UnsupportedAPIVersion

   .. versionadded:: 2023.0.0


.. autoexception:: APIVersionWarning

   .. versionadded:: 2023.0.0

.. autoexception:: UnsupportedMIMEType

   .. versionadded:: 2022.1.0

.. autodata:: ProjectIndex_1_0
   :no-value:

   .. versionadded:: 2022.0.0


.. autodata:: ProjectIndex_1_1
   :no-value:

   .. versionadded:: 2022.1.0

.. data:: ProjectIndex

   A :data:`~typing.TypeAlias` for any version of the JSON project index response.

   .. versionadded:: 2022.0.0
   .. versionchanged:: 2022.1.0
      Added :data:`ProjectIndex_1_1`.

.. autodata:: ProjectFileDetails_1_0
   :no-value:

   .. versionadded:: 2022.0.0

.. autodata:: ProjectFileDetails_1_1
   :no-value:

   .. versionadded:: 2022.1.0

.. autodata:: ProjectDetails_1_0
   :no-value:

   .. versionadded:: 2022.0.0

.. autodata:: ProjectDetails_1_1
   :no-value:

   .. versionadded:: 2022.1.0

.. data:: ProjectDetails

   A :data:`~typing.TypeAlias` for any version of the JSON project details response.

   .. versionadded:: 2022.0.0
   .. versionchanged:: 2022.1.0
      Added :data:`ProjectDetails_1_1`.

.. autofunction:: from_project_index_html

   .. versionadded:: 2022.0.0

.. autofunction:: create_project_url

   .. versionadded:: 2022.0.0

.. autofunction:: from_project_details_html

   .. versionadded:: 2022.0.0

.. autofunction:: parse_project_index

   .. versionadded:: 2022.1.0

.. autofunction:: parse_project_details

   .. versionadded:: 2022.1.0
